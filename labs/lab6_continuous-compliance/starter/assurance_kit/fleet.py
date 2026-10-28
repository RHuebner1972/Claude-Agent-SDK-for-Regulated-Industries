"""The fleet manifest: every deployed agent's model, prompt, tools, controls and control configs, in one file.

An agent's FINGERPRINT is a hash of everything that changes its behavior: model, prompt version, permission mode,
tool allowlist, control settings, and the name@version of each control config. Change any of them and the
fingerprint changes, so change control can ask: is there an approved, re-validated change record for this?
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

import sentinel

SENTINEL = Path(sentinel.__file__).resolve().parent          # config paths in the manifest are relative to this
FLEET_PATH = Path(__file__).parent / "policies" / "fleet.yaml"


class FleetAgent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    lab: str
    organization: str
    owner: str
    risk_tier: int = Field(ge=1, le=4)
    model: str
    prompt_version: str
    permission_mode: Literal["default", "acceptEdits", "plan", "dontAsk", "auto", "bypassPermissions"]
    tools: list[str]
    controls: dict[str, Any] = Field(default_factory=dict)
    configs: list[str] = Field(default_factory=list)

    def config_paths(self) -> list[Path]:
        return [p if (p := Path(c)).is_absolute() else SENTINEL / c for c in self.configs]

    def config_versions(self) -> dict[str, str]:
        """name@version declared inside each control config (policy, oversight rules, agent cards)."""
        out = {}
        for path in self.config_paths():
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            out[path.name] = f"{doc.get('name', path.stem)}@{doc.get('version', 'unversioned')}"
        return out

    def fingerprint_inputs(self) -> dict[str, Any]:
        return {"model": self.model, "prompt_version": self.prompt_version, "permission_mode": self.permission_mode,
                "tools": sorted(self.tools), "controls": self.controls, "configs": self.config_versions()}

    def fingerprint(self) -> str:
        blob = json.dumps(self.fingerprint_inputs(), sort_keys=True, separators=(",", ":"))
        return "fp:" + hashlib.sha256(blob.encode()).hexdigest()[:16]


class Fleet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str
    agents: list[FleetAgent]
    path: str = ""

    def get(self, name: str) -> FleetAgent:
        agent = next((a for a in self.agents if a.name == name), None)
        if agent is None:
            raise KeyError(f"no agent {name!r} in the fleet manifest")
        return agent

    def fingerprints(self) -> dict[str, str]:
        return {a.name: a.fingerprint() for a in self.agents}


def load_fleet(path: str | Path | None = None) -> Fleet:
    """Load the manifest. FLEET_FILE overrides the default (CI uses it to test a proposed change)."""
    path = Path(path or os.getenv("FLEET_FILE") or FLEET_PATH)
    return Fleet.model_validate({**yaml.safe_load(path.read_text(encoding="utf-8")), "path": str(path)})
