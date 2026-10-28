"""Choose a deployment path from regulatory requirements (M10-L01, L07).

The facts live in policies/deployment_paths.yaml with an as_of date; this module only filters them. The output is a
SHORTLIST with reasons, not a decision: contracts, model availability and your own risk assessment come next.

    from sentinel.deploy import Requirements, shortlist
    for fit in shortlist(Requirements(phi=True, fedramp="high")):
        print(fit.path, fit.ok, fit.reasons)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

PATHS_FILE = Path(__file__).parent / "policies" / "deployment_paths.yaml"
FEDRAMP_RANK = {"none": 0, "moderate": 1, "high": 2}


class PathFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str
    processor: str
    phi: str
    hipaa: bool | Literal["ask"]           # "ask": not documented either way; confirm with the vendor
    zdr: str
    us_residency: str
    eu_residency: bool
    fedramp: Literal["none", "moderate", "high"]
    il: int
    itar: bool
    private_networking: str
    sdk_env: dict[str, str]
    endpoint: str
    source: str
    note: str = ""


class PathCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    as_of: str
    paths: dict[str, PathFacts]


class Requirements(BaseModel):
    """What the data and the customer demand. Every field is a question for your compliance partner."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    phi: bool = False
    fedramp: Literal["none", "moderate", "high"] = "none"
    il: int = 0                      # DoD impact level, 0 if none
    itar: bool = False
    eu_residency: bool = False
    us_residency: bool = False
    private_network: bool = False    # traffic must not cross the public internet
    cloud_processor: bool = False    # the cloud provider (not the model vendor) must be the data processor


@dataclass
class Fit:
    path: str
    title: str
    ok: bool
    reasons: list[str] = field(default_factory=list)
    to_confirm: list[str] = field(default_factory=list)


def load_catalog(path: str | Path = PATHS_FILE) -> PathCatalog:
    return PathCatalog.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def assess(name: str, facts: PathFacts, req: Requirements) -> Fit:
    fit = Fit(name, facts.title, True)
    no = lambda why: (fit.reasons.append(why), setattr(fit, "ok", False))
    if req.phi and facts.hipaa is False:
        no("no HIPAA coverage for PHI on this path")
    if FEDRAMP_RANK[facts.fedramp] < FEDRAMP_RANK[req.fedramp]:
        no(f"FedRAMP {facts.fedramp}, need {req.fedramp}")
    if req.il and facts.il < req.il:
        no(f"impact level {facts.il or 'none'}, need IL{req.il}")
    if req.itar and not facts.itar:
        no("not a route for ITAR-controlled data")
    if req.eu_residency and not facts.eu_residency:
        no("no EU residency option")
    if req.eu_residency and req.fedramp != "none":
        no("FedRAMP-authorized environments are US regions: EU residency needs a separate deployment")
    if req.cloud_processor and facts.processor == "Anthropic":
        no("Anthropic, not your cloud provider, processes the data")
    if req.private_network and ("PrivateLink" not in facts.private_networking
                                and "Private Service Connect" not in facts.private_networking):
        no("no documented private endpoint")
    if fit.ok:
        fit.reasons.append(f"processor: {facts.processor}")
        if req.phi:
            fit.to_confirm.append(f"agreement: {facts.phi}" if facts.hipaa is True
                                  else f"PHI coverage isn't documented: {facts.phi}")
        if req.us_residency:
            fit.to_confirm.append(f"US residency: {facts.us_residency}")
        fit.to_confirm.append(f"retention: {facts.zdr}")
        if facts.note:
            fit.to_confirm.append(facts.note)
    return fit


def shortlist(req: Requirements, catalog: PathCatalog | None = None) -> list[Fit]:
    catalog = catalog or load_catalog()
    fits = [assess(n, f, req) for n, f in catalog.paths.items()]
    return sorted(fits, key=lambda f: (not f.ok, f.path))
