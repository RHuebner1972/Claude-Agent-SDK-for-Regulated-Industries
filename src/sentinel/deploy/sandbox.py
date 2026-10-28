"""Sandbox the agent runtime: container hardening, filesystem scope and network egress (rubric 3.5, M10-L04).

Three layers, each enforced OUTSIDE the model's reach:
  1. The container: non-root, read-only root filesystem, all Linux capabilities dropped, no network interface;
     the only way out is a proxy socket (the pattern in Anthropic's secure-deployment guide).
  2. The egress proxy: a domain allowlist (the model endpoint plus whatever the tools truly need). It also injects
     credentials, so the agent never holds them (identity.py).
  3. Inside the agent: a PreToolUse filesystem guard for file tools, and the SDK's own sandbox settings for Bash
     (the SDK sandbox covers Bash and the processes it starts, not Read/Write/Edit or MCP tools).

    profile = load_deployment().get("aml-triage").sandbox
    print(" ".join(docker_args(profile)))
"""
from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

CREDENTIAL_PATTERNS = [".env", ".env.*", "*.pem", "*.key", "*-service-account.json", ".git-credentials",
                       ".aws/*", ".azure/*", ".config/gcloud/*", ".kube/config", ".docker/config.json", ".npmrc",
                       ".pypirc", ".ssh/*"]


class Mount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str
    target: str
    read_only: bool = True


class SandboxProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    image: str
    runtime: Literal["runc", "runsc"] = "runc"          # runsc = gVisor: syscalls intercepted in user space
    user: str = "1000:1000"
    read_only_root: bool = True
    cap_drop_all: bool = True
    no_new_privileges: bool = True
    seccomp_profile: str | None = None
    network: Literal["none", "bridge", "host"] = "none"
    proxy_socket: str = "/var/run/egress-proxy.sock"
    tmpfs: dict[str, str] = Field(default_factory=lambda: {"/tmp": "rw,noexec,nosuid,size=100m"})
    mounts: list[Mount] = Field(default_factory=list)
    memory: str = "2g"
    cpus: float = 1.0
    pids_limit: int = 100
    egress_allowlist: list[str]
    workspace: str = "/workspace"


def docker_args(p: SandboxProfile, name: str = "agent") -> list[str]:
    """The `docker run` flags for a profile: the hardened baseline from Anthropic's secure-deployment guide."""
    args = ["docker", "run", "--rm", "--name", name]
    if p.runtime == "runsc":
        args += ["--runtime=runsc"]
    if p.cap_drop_all:
        args += ["--cap-drop", "ALL"]
    if p.no_new_privileges:
        args += ["--security-opt", "no-new-privileges"]
    if p.seccomp_profile:
        args += ["--security-opt", f"seccomp={p.seccomp_profile}"]
    if p.read_only_root:
        args += ["--read-only"]
    for path, opts in p.tmpfs.items():
        args += ["--tmpfs", f"{path}:{opts}"]
    args += ["--network", p.network, "--memory", p.memory, "--cpus", str(p.cpus), "--pids-limit", str(p.pids_limit),
             "--user", p.user]
    for m in p.mounts:
        args += ["-v", f"{m.source}:{m.target}{':ro' if m.read_only else ''}"]
    args += ["-v", f"{p.proxy_socket}:{p.proxy_socket}:ro", p.image]
    return args


SENSITIVE_HOST_PATHS = ("~/.ssh", "~/.aws", "~/.config", "~/.azure", "~/.kube", "/var/run/docker.sock", "/")


def lint_profile(p: SandboxProfile, model_endpoint: str | None = None) -> list[str]:
    """Findings a security reviewer would raise. Empty list = the profile meets the course baseline."""
    f = []
    if p.user.split(":")[0] in ("0", "root"):
        f.append("SBX-001 runs as root")
    if not p.read_only_root:
        f.append("SBX-002 root filesystem is writable")
    if not p.cap_drop_all:
        f.append("SBX-003 Linux capabilities not dropped")
    if not p.no_new_privileges:
        f.append("SBX-004 setuid privilege escalation not blocked (no-new-privileges)")
    if p.network != "none":
        f.append(f"SBX-005 network '{p.network}': the agent can reach the network without the proxy")
    for m in p.mounts:
        if m.source in SENSITIVE_HOST_PATHS or any(m.source.startswith(s + "/") for s in SENSITIVE_HOST_PATHS[:5]):
            f.append(f"SBX-006 mounts a sensitive host path: {m.source}")
        if not m.read_only and m.target != p.workspace:
            f.append(f"SBX-007 writable mount outside the workspace: {m.target}")
    if any("*" == d or d.startswith("*.") and d.count(".") < 2 for d in p.egress_allowlist):
        f.append("SBX-008 egress allowlist has a wildcard that covers a whole public suffix")
    if model_endpoint and model_endpoint not in p.egress_allowlist:
        f.append(f"SBX-009 model endpoint {model_endpoint} is not on the egress allowlist")
    return f


# ---------------------------------------------------------------------------------------------- egress proxy
@dataclass
class EgressDecision:
    url: str
    host: str
    allowed: bool
    reason: str


class EgressPolicy:
    """The proxy's allowlist check. Exact hosts, or '*.example.com' for subdomains (never the bare suffix)."""

    def __init__(self, allowlist: list[str]):
        self.allowlist = [d.lower().rstrip(".") for d in allowlist]

    def check(self, url: str) -> EgressDecision:
        parts = urlsplit(url if "://" in url else "https://" + url)
        host = (parts.hostname or "").lower().rstrip(".")
        if parts.scheme != "https":
            return EgressDecision(url, host, False, f"scheme {parts.scheme!r}: only https leaves the sandbox")
        try:
            ipaddress.ip_address(host)
            return EgressDecision(url, host, False, "IP literal: hosts must be named so the allowlist applies")
        except ValueError:
            pass
        for rule in self.allowlist:
            if host == rule or (rule.startswith("*.") and host.endswith(rule[1:]) and host != rule[2:]):
                return EgressDecision(url, host, True, f"matches {rule}")
        return EgressDecision(url, host, False, "not on the egress allowlist")


# ---------------------------------------------------------------------------------------------- filesystem
def _matches_credential(path: PurePosixPath) -> str | None:
    text = str(path)
    for pat in CREDENTIAL_PATTERNS:
        if fnmatch.fnmatch(path.name, pat) or fnmatch.fnmatch(text, "*/" + pat):
            return pat
    return None


class FsGuard:
    """PreToolUse hook for file tools: reads inside read_roots, writes inside write_roots, never credentials."""

    FILE_TOOLS = {"Read": "read", "Glob": "read", "Grep": "read", "Write": "write", "Edit": "write",
                  "NotebookEdit": "write"}

    def __init__(self, read_roots: list[str], write_roots: list[str]):
        self.read_roots = [PurePosixPath(r) for r in read_roots]
        self.write_roots = [PurePosixPath(r) for r in write_roots]

    @staticmethod
    def _within(path: PurePosixPath, roots: list[PurePosixPath]) -> bool:
        return any(path == r or r in path.parents for r in roots)

    def decide(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
        mode = self.FILE_TOOLS.get(tool_name)
        if mode is None:
            return "allow", "not a file tool"
        raw = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path") or "."
        path = PurePosixPath(raw)
        if ".." in path.parts or not path.is_absolute():
            return "deny", f"FS-001 path must be absolute and normalized: {raw}"
        if (pat := _matches_credential(path)) is not None:
            return "deny", f"FS-002 credential file pattern {pat}: {raw}"
        roots = self.write_roots if mode == "write" else self.read_roots + self.write_roots
        if not self._within(path, roots):
            return "deny", f"FS-003 {mode} outside the sandbox roots: {raw}"
        return "allow", f"{mode} inside {'write' if mode == 'write' else 'read'} roots"

    async def __call__(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        decision, reason = self.decide(input_data.get("tool_name", ""), input_data.get("tool_input") or {})
        if decision == "allow":
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}


def sdk_sandbox_settings(p: SandboxProfile) -> dict[str, Any]:
    """Settings for the Agent SDK's Bash sandbox (ClaudeAgentOptions(sandbox=...) / settings 'sandbox' key).

    Belt and braces: the container already has no network, but if Bash is ever enabled, sandboxed commands get the
    same allowlist, no unsandboxed retries, and the session fails closed if the sandbox can't start.
    """
    return {"enabled": True, "failIfUnavailable": True, "autoAllowBashIfSandboxed": False,
            "allowUnsandboxedCommands": False, "excludedCommands": [],
            "network": {"allowedDomains": list(p.egress_allowlist), "strictAllowlist": True},
            "filesystem": {"allowWrite": [p.workspace], "denyRead": ["~/"], "allowRead": [p.workspace]}}
