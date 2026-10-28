"""Retention and deletion for what an agent leaves behind (rubric 1.4 and 2.6, M10-L03).

Two opposite duties, one module:
  KEEP   audit logs and approval records for at least the period the regulation sets, where nobody (including an
         administrator) can alter or delete them early: write-once storage with a retention lock (rubric 1.4).
  DELETE session transcripts and caches as soon as their purpose ends, provably, unless a legal hold applies
         (rubric 2.6). Transcripts hold whatever the model saw, which can include PHI and client data.

WormStore is a LOCAL STAND-IN for the real thing (S3 Object Lock in compliance mode, Azure immutable blob storage,
Google Cloud Storage bucket lock). It enforces the same rules in code so the course runs offline; in production the
cloud service enforces them, and the deployment config says which service and mode (see deployment.py).

TranscriptStore implements the Agent SDK's SessionStore protocol (append / load / list_sessions / delete /
list_subkeys), so you can pass it as ClaudeAgentOptions(session_store=...) and the SDK mirrors transcripts into
storage you govern. The SDK never deletes from a store on its own: retention is your job, and sweep() does it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sentinel.audit import AuditStore
from sentinel.audit.models import Actor, AgentInfo, AuditEvent

DataClass = Literal["audit_log", "approval_record", "session_transcript", "tool_cache", "provider_prompt_cache",
                    "vault_entry", "evidence_pack"]
Clock = Callable[[], datetime]
utcnow: Clock = lambda: datetime.now(timezone.utc)                       # noqa: E731


class RetentionLocked(Exception):
    """Raised when someone tries to change or delete a record before its retention allows it."""


class RetentionRule(BaseModel):
    """How long one class of data lives. min_days = must keep at least; max_days = must delete by."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_class: DataClass
    min_days: int = Field(default=0, ge=0)
    max_days: int | None = Field(default=None, ge=0)
    worm: bool = False                       # stored write-once with a retention lock
    basis: str = Field(min_length=5)         # the regulation, contract or policy that sets the period
    where: str = ""                          # system of record

    @model_validator(mode="after")
    def _coherent(self) -> "RetentionRule":
        if self.max_days is not None and self.max_days < self.min_days:
            raise ValueError(f"{self.data_class}: max_days {self.max_days} < min_days {self.min_days}")
        if self.worm and not self.min_days:
            raise ValueError(f"{self.data_class}: a WORM rule needs a minimum retention period")
        if self.data_class == "session_transcript" and self.max_days is None:
            raise ValueError("session transcripts need a max_days: they hold whatever the model saw")
        return self


# ------------------------------------------------------------------------------------------------ keep (1.4)
@dataclass
class ObjectMeta:
    key: str
    sha256: str
    created: str
    retain_until: str
    legal_hold: bool = False
    mode: str = "COMPLIANCE"


class WormStore:
    """Write-once, retention-locked object storage (local stand-in for S3 Object Lock, compliance mode)."""

    def __init__(self, root: str | Path, clock: Clock = utcnow):
        self.root, self.clock = Path(root), clock
        (self.root / ".meta").mkdir(parents=True, exist_ok=True)

    def _meta_path(self, key: str) -> Path:
        return self.root / ".meta" / (key.replace("/", "__") + ".json")

    def meta(self, key: str) -> ObjectMeta:
        return ObjectMeta(**json.loads(self._meta_path(key).read_text(encoding="utf-8")))

    def _save(self, m: ObjectMeta) -> None:
        self._meta_path(m.key).write_text(json.dumps(asdict(m)), encoding="utf-8")

    def keys(self) -> list[str]:
        return sorted(json.loads(p.read_text(encoding="utf-8"))["key"] for p in (self.root / ".meta").glob("*.json"))

    def put(self, key: str, data: bytes, retain_days: int) -> ObjectMeta:
        if self._meta_path(key).exists():
            raise RetentionLocked(f"{key}: objects are write-once; a new version needs a new key")
        if retain_days <= 0:
            raise ValueError("a retention-locked object needs a positive retention period")
        now = self.clock()
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        m = ObjectMeta(key, "sha256:" + hashlib.sha256(data).hexdigest(), now.isoformat(),
                       (now + timedelta(days=retain_days)).isoformat())
        self._save(m)
        return m

    def get(self, key: str) -> bytes:
        data, m = (self.root / key).read_bytes(), self.meta(key)
        if "sha256:" + hashlib.sha256(data).hexdigest() != m.sha256:
            raise RetentionLocked(f"{key}: content no longer matches the hash recorded at write time")
        return data

    def overwrite(self, key: str, data: bytes) -> None:
        raise RetentionLocked(f"{key}: overwrite refused (write-once)")

    def extend(self, key: str, retain_until: datetime) -> ObjectMeta:
        m = self.meta(key)
        if retain_until <= datetime.fromisoformat(m.retain_until):
            raise RetentionLocked(f"{key}: retention can be extended, never shortened")
        m.retain_until = retain_until.isoformat()
        self._save(m)
        return m

    def set_legal_hold(self, key: str, on: bool) -> ObjectMeta:
        m = self.meta(key)
        m.legal_hold = on
        self._save(m)
        return m

    def delete(self, key: str) -> None:
        m = self.meta(key)
        if m.legal_hold:
            raise RetentionLocked(f"{key}: under legal hold")
        if self.clock() < datetime.fromisoformat(m.retain_until):
            raise RetentionLocked(f"{key}: retained until {m.retain_until[:10]} (compliance mode: no one can delete "
                                  "it earlier, including administrators)")
        (self.root / key).unlink()
        self._meta_path(key).unlink()

    def verify(self) -> list[str]:
        problems = []
        for key in self.keys():
            try:
                self.get(key)
            except (RetentionLocked, FileNotFoundError) as exc:
                problems.append(str(exc))
        return problems


def archive_audit_log(store: WormStore, log: Path, agent: str, rule: RetentionRule) -> list[ObjectMeta]:
    """Ship a run's audit log and its signed checkpoints to WORM storage under the agent's retention rule."""
    if not rule.worm or rule.data_class != "audit_log":
        raise ValueError("archive_audit_log needs the agent's WORM audit_log rule")
    out = []
    batch = f"{agent}/{store.clock():%Y-%m-%d}/{hashlib.sha256(log.read_bytes()).hexdigest()[:12]}"
    for path in (log, log.with_name(log.stem + ".checkpoints.jsonl")):
        if path.exists():
            out.append(store.put(f"{batch}/{path.name}", path.read_bytes(), rule.min_days))
    return out


# ---------------------------------------------------------------------------------------------- delete (2.6)
class TranscriptStore:
    """A filesystem SessionStore for the Agent SDK: transcripts land in storage you govern, and sweep() deletes them.

    ClaudeAgentOptions(session_store=TranscriptStore(root), env={"CLAUDE_CONFIG_DIR": <temp dir>}) keeps the
    SDK's own local copy out of the long-lived filesystem (see session_options()).
    """

    def __init__(self, root: str | Path, clock: Clock = utcnow):
        self.root, self.clock = Path(root), clock

    def _file(self, key: dict) -> Path:
        name = key["session_id"] + ("/" + key["subpath"] if key.get("subpath") else "") + ".jsonl"
        return self.root / key["project_key"] / name

    async def append(self, key: dict, entries: list[dict]) -> None:
        path = self._file(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        seen = {json.loads(line).get("uuid") for line in path.read_text(encoding="utf-8").splitlines()} \
            if path.exists() else set()
        with path.open("a", encoding="utf-8") as f:
            for e in entries:
                if e.get("uuid") is None or e["uuid"] not in seen:   # retried batches can re-deliver entries
                    f.write(json.dumps(e) + "\n")
        self._touch(key)

    async def load(self, key: dict) -> list[dict] | None:
        path = self._file(key)
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else None

    async def list_sessions(self, project_key: str) -> list[dict]:
        idx = self._index(project_key)
        return [{"session_id": s, "mtime": m} for s, m in sorted(idx.items())]

    async def delete(self, key: dict) -> None:
        """Deleting the main key cascades to subagent transcripts (the SDK's contract)."""
        base = self.root / key["project_key"]
        main = base / (key["session_id"] + ".jsonl")
        if main.exists():
            main.unlink()
        sub = base / key["session_id"]
        if sub.exists():
            for p in sorted(sub.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
            sub.rmdir()
        idx = self._index(key["project_key"])
        idx.pop(key["session_id"], None)
        self._save_index(key["project_key"], idx)

    async def list_subkeys(self, key: dict) -> list[str]:
        sub = self.root / key["project_key"] / key["session_id"]
        return sorted(str(p.relative_to(sub).with_suffix("")) for p in sub.rglob("*.jsonl")) if sub.exists() else []

    # index of session -> mtime (ms), on the store's clock so the sweep is testable
    def _index_path(self, project_key: str) -> Path:
        return self.root / project_key / ".index.json"

    def _index(self, project_key: str) -> dict[str, int]:
        p = self._index_path(project_key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def _save_index(self, project_key: str, idx: dict[str, int]) -> None:
        p = self._index_path(project_key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(idx), encoding="utf-8")

    def _touch(self, key: dict) -> None:
        if key.get("subpath"):
            return
        idx = self._index(key["project_key"])
        idx[key["session_id"]] = int(self.clock().timestamp() * 1000)
        self._save_index(key["project_key"], idx)

    def projects(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir()) if self.root.exists() else []

    def digest(self, key: dict) -> str:
        h = hashlib.sha256()
        for p in [self._file(key)] + sorted((self.root / key["project_key"] / key["session_id"]).rglob("*.jsonl")):
            if p.exists():
                h.update(p.read_bytes())
        return "sha256:" + h.hexdigest()


@dataclass
class DeletionReceipt:
    """Proof of deletion without keeping the content: what, when, under which rule, and a hash of what was deleted."""
    agent: str
    data_class: str
    session_id: str
    age_days: float
    content_sha256: str
    rule_basis: str
    deleted_at: str


def sweep(store: TranscriptStore, agent: str, rule: RetentionRule, *, holds: set[str] = frozenset(),
          audit: AuditStore | None = None, policy_version: str = "deployment") -> list[DeletionReceipt]:
    """Delete every transcript older than the rule's max_days, except sessions under legal hold.

    Each deletion is recorded as a decision in the audit trail: the transcript is gone, the receipt is not.
    """
    import asyncio

    if rule.data_class != "session_transcript" or rule.max_days is None:
        raise ValueError("sweep needs a session_transcript rule with max_days")
    now = store.clock()
    receipts = []
    for project in store.projects():
        for entry in asyncio.run(store.list_sessions(project)):
            age = (now.timestamp() * 1000 - entry["mtime"]) / 86_400_000
            if age < rule.max_days or entry["session_id"] in holds:
                continue
            key = {"project_key": project, "session_id": entry["session_id"]}
            digest = store.digest(key)
            asyncio.run(store.delete(key))
            r = DeletionReceipt(agent, rule.data_class, entry["session_id"], round(age, 2), digest, rule.basis,
                                now.isoformat())
            receipts.append(r)
            if audit is not None:
                audit.append(_deletion_event(r, policy_version))
    return receipts


def _deletion_event(r: DeletionReceipt, policy_version: str) -> AuditEvent:
    return AuditEvent(event_type="decision.recorded", actor=Actor(kind="system", id="retention-sweeper"),
                      on_behalf_of="records-management", correlation_id=f"sweep-{r.deleted_at[:10]}",
                      agent=AgentInfo(name=r.agent, version="retention-sweeper/1.0", model="n/a",
                                      prompt_version="n/a", policy_version=policy_version),
                      outcome="success", reason=f"{r.data_class} older than its maximum retention",
                      authority=r.rule_basis,
                      detail={"action": "deleted", "data_class": r.data_class, "session_id": r.session_id,
                              "age_days": r.age_days, "content_sha256": r.content_sha256})


def session_options(store: TranscriptStore, config_dir: str | Path) -> dict[str, Any]:
    """Keyword arguments for ClaudeAgentOptions so transcripts go to the governed store, not ~/.claude.

    config_dir should be a per-session temporary directory you delete when the session ends.
    """
    return {"session_store": store,
            "env": {"CLAUDE_CONFIG_DIR": str(config_dir), "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},     # no telemetry or error reports
            "setting_sources": []}
