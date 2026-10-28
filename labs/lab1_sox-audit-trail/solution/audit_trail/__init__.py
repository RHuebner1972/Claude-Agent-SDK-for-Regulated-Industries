"""Lab 1 solution: the audit trail package (same design as sentinel.audit, which later modules import)."""
from .hashing import GENESIS, canonical, record_hash, sha256_hex, sign, signature_ok
from .hooks import AuditHooks, new_correlation_id
from .models import Actor, AgentInfo, AuditEvent, content_version
from .redact import fingerprint, redact, response_text, summarize
from .replay import replay_decision
from .store import AuditStore
from .verify import VerifyReport, verify_log

__all__ = [
    "Actor", "AgentInfo", "AuditEvent", "AuditHooks", "AuditStore", "GENESIS", "VerifyReport",
    "canonical", "content_version", "fingerprint", "new_correlation_id", "record_hash", "redact", "replay_decision",
    "response_text", "sha256_hex", "sign", "signature_ok", "summarize", "verify_log",
]
