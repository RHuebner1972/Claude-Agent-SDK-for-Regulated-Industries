"""The deployment manifest (policies/deployment.yaml) and the pre-flight check (M10-L08).

For each agent it declares WHERE Claude runs (path, region, endpoint), UNDER WHAT AGREEMENTS (BAA, DPA), what the
data DEMANDS (PHI, FedRAMP, ITAR, residency), and the runtime controls: retention rules and WORM audit storage,
the workload identity, and the sandbox profile. preflight() checks that all of it hangs together before anything
ships. The production fleet manifest (fleet-prod.yaml) lists this file in every agent's configs, so editing it
changes every fingerprint and needs a change record (rubric 7.4).

    python -m sentinel.deploy preflight
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from sentinel.monitoring.fleet import Fleet

from .identity import WorkloadIdentity
from .paths import PathCatalog, Requirements, assess, load_catalog
from .retention import RetentionRule
from .sandbox import SandboxProfile, lint_profile

DEPLOYMENT_FILE = Path(__file__).parent / "policies" / "deployment.yaml"
PROD_FLEET = Path(__file__).resolve().parents[1] / "monitoring" / "policies" / "fleet-prod.yaml"


class AuditStorage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    service: str                                          # "S3 Object Lock", "Azure immutable blob", "GCS bucket lock"
    mode: Literal["COMPLIANCE", "GOVERNANCE"]             # governance mode can be bypassed with a special permission
    location: str
    retain_days: int = Field(gt=0)


class AgentDeployment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    region: str
    endpoint: str
    requirements: Requirements
    agreements: list[str]
    audit_storage: AuditStorage
    retention: list[RetentionRule]
    identity: WorkloadIdentity
    sandbox: SandboxProfile
    notes: str = ""

    def rule(self, data_class: str) -> RetentionRule | None:
        return next((r for r in self.retention if r.data_class == data_class), None)

    @model_validator(mode="after")
    def _one_rule_per_class(self) -> "AgentDeployment":
        classes = [r.data_class for r in self.retention]
        if len(classes) != len(set(classes)):
            raise ValueError(f"duplicate retention rules: {classes}")
        return self


class Deployment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    as_of: str
    agents: dict[str, AgentDeployment]

    def get(self, agent: str) -> AgentDeployment:
        if agent not in self.agents:
            raise KeyError(f"{agent} has no entry in the deployment manifest")
        return self.agents[agent]


def load_deployment(path: str | Path = DEPLOYMENT_FILE) -> Deployment:
    return Deployment.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def check_agent(name: str, d: AgentDeployment, catalog: PathCatalog) -> list[str]:
    """Pre-flight findings for one agent. Empty list = ready to ship (as far as configuration can tell)."""
    f: list[str] = []
    if d.path not in catalog.paths:
        return [f"DEP-001 {name}: unknown deployment path {d.path!r}"]
    fit = assess(d.path, catalog.paths[d.path], d.requirements)
    f += [f"DEP-002 {name}: {d.path} doesn't meet the requirements: {r}" for r in ([] if fit.ok else fit.reasons)]
    if d.requirements.phi and not any("BAA" in a or "Business Associate Agreement" in a for a in d.agreements):
        f.append(f"DEP-003 {name}: PHI in scope but no business associate agreement listed")
    audit = d.rule("audit_log")
    if audit is None or not audit.worm:
        f.append(f"DEP-004 {name}: no WORM retention rule for the audit log")
    elif d.audit_storage.mode != "COMPLIANCE":
        f.append(f"DEP-005 {name}: audit storage in {d.audit_storage.mode} mode can be shortened by an admin")
    elif d.audit_storage.retain_days < audit.min_days:
        f.append(f"DEP-006 {name}: storage locks {d.audit_storage.retain_days} days, rule needs {audit.min_days}")
    if d.rule("session_transcript") is None:
        f.append(f"DEP-007 {name}: no retention rule for session transcripts")
    if name not in d.identity.principal:
        f.append(f"DEP-008 {name}: identity {d.identity.principal} isn't this agent's own principal")
    if d.identity.max_ttl_s > 900:
        f.append(f"DEP-009 {name}: credentials live {d.identity.max_ttl_s}s; the course baseline is 15 minutes")
    f += [f"{x.split(' ', 1)[0]} {name}: {x.split(' ', 1)[1]}" for x in lint_profile(d.sandbox, d.endpoint)]
    return f


def preflight(fleet: Fleet, deployment: Deployment | None = None,
              catalog: PathCatalog | None = None) -> dict[str, list[str]]:
    """Every agent that declares a production deployment must pass check_agent()."""
    deployment, catalog = deployment or load_deployment(), catalog or load_catalog()
    out = {}
    for agent in fleet.agents:
        if not agent.controls.get("deployment"):
            out[agent.name] = [f"DEP-000 {agent.name}: no production deployment declared in the fleet manifest"]
        elif agent.name not in deployment.agents:
            out[agent.name] = [f"DEP-001 {agent.name}: declared deployed but missing from deployment.yaml"]
        else:
            out[agent.name] = check_agent(agent.name, deployment.get(agent.name), catalog)
    return out


# ------------------------------------------------------------------------------------- reference architecture
SECRET_ENV = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")


def check_reference(folder: str | Path, agent: str, deployment: Deployment | None = None) -> list[str]:
    """Static checks on a compose-based reference deployment (compose.yaml + egress-proxy/squid.conf).

    The agent service must be hardened, sit only on internal networks, hold no secrets, and reach the outside only
    through services that are on both an internal and an egress network. The proxy's allowlist must be a subset of
    the agent's declared egress allowlist.
    """
    folder = Path(folder)
    d = (deployment or load_deployment()).get(agent)
    doc = yaml.safe_load((folder / "compose.yaml").read_text(encoding="utf-8"))
    services, networks = doc.get("services", {}), doc.get("networks", {})
    a = services.get("agent")
    if a is None:
        return ["REF-000 no 'agent' service"]
    f = []
    if str(a.get("user", "0")).split(":")[0] in ("0", "root"):
        f.append("REF-001 agent runs as root")
    if not a.get("read_only"):
        f.append("REF-002 agent root filesystem is writable")
    if "ALL" not in a.get("cap_drop", []):
        f.append("REF-003 agent keeps Linux capabilities")
    if not any(str(o).startswith("no-new-privileges") for o in a.get("security_opt", [])):
        f.append("REF-004 no-new-privileges not set")
    if a.get("ports"):
        f.append("REF-005 agent publishes ports: put it behind the authenticating gateway instead")
    internal = {n for n, cfg in networks.items() if (cfg or {}).get("internal")}
    outside = [n for n in a.get("networks", []) if n not in internal]
    if outside or not a.get("networks"):
        f.append(f"REF-006 agent is attached to a network with an internet route: {outside or 'default'}")
    env = a.get("environment", {}) or {}
    for k, v in env.items():
        if any(s in k.upper() for s in SECRET_ENV) and "SKIP" not in k.upper():
            f.append(f"REF-007 secret-shaped variable in the agent environment: {k}")
    if not env.get("HTTPS_PROXY"):
        f.append("REF-008 HTTPS_PROXY not set: tools would try to connect directly (and fail closed)")
    exits = [n for n, s in services.items() if n != "agent"
             and set(s.get("networks", [])) & internal and set(s.get("networks", [])) - internal]
    if not exits:
        f.append("REF-009 no egress service bridges the internal network")
    squid = folder / "egress-proxy" / "squid.conf"
    if squid.exists():
        allowed = [h for line in squid.read_text(encoding="utf-8").splitlines()
                   if line.startswith("acl allowed_hosts dstdomain") for h in line.split()[3:]]
        extra = sorted(set(allowed) - set(d.sandbox.egress_allowlist))
        if extra:
            f.append(f"REF-010 proxy allows hosts the deployment manifest doesn't: {extra}")
        if "http_access deny all" not in squid.read_text(encoding="utf-8"):
            f.append("REF-011 proxy doesn't end with 'http_access deny all'")
    else:
        f.append("REF-012 no egress proxy configuration")
    if d.sandbox.image.split("@")[0] not in str(a.get("image", "")) or "@sha256:" not in str(a.get("image", "")):
        f.append("REF-013 agent image isn't the manifest's image pinned by digest")
    return f
