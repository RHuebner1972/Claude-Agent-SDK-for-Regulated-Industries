"""An append-only, hash-chained JSONL audit store with optional signed checkpoints.

Each line carries seq, prev_hash and hash. Change any line and its hash no longer matches;
recompute that hash and the NEXT line's prev_hash no longer matches. Rewriting the whole
chain, or deleting the tail, is caught by the HMAC-signed checkpoints (only a key holder
can sign) and, in production, by shipping checkpoints to WORM storage you don't control.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .hashing import GENESIS, canonical, record_hash, sign
from .models import AuditEvent


class AuditStore:
    def __init__(self, path: str | Path, *, hmac_key: bytes | None = None, checkpoint_every: int = 0,
                 clock: Callable[[], datetime] | None = None):
        self.path = Path(path)
        self.checkpoint_path = self.path.with_name(self.path.stem + ".checkpoints.jsonl")
        self.hmac_key = hmac_key
        self.checkpoint_every = checkpoint_every
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._head = self._resume()
        self._size = self.path.stat().st_size if self.path.exists() else 0

    def _resume(self) -> tuple[int, str]:
        """Continue an existing chain instead of starting a second one in the same file."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0, GENESIS
        last = self.path.read_text(encoding="utf-8").rstrip("\n").splitlines()[-1]
        record = json.loads(last)
        return int(record["seq"]), str(record["hash"])

    @property
    def head(self) -> str:
        return self._head

    def append(self, event: AuditEvent) -> AuditEvent:
        """Seal the event into the chain and write it. Returns the sealed event."""
        # TODO 1 (walkthrough part 1): seal the event into the chain.
        # 1. Under self._lock, copy the event with seq = self._seq + 1, prev_hash = self._head, hash = None.
        # 2. record = sealed.model_dump(mode="json"); record["hash"] = record_hash(record)
        # 3. Open self.path in APPEND-BINARY mode, write canonical(record) + b"\n", flush, os.fsync.
        # 4. Update self._seq and self._head. If a key is set and seq % checkpoint_every == 0, write a checkpoint.
        # 5. Return the sealed event with its hash filled in.
        raise NotImplementedError("Lab 1: append")

    def checkpoint(self) -> dict | None:
        """Sign the current head. Call at the end of every run (and on a timer in production)."""
        with self._lock:
            return self._write_checkpoint() if self.hmac_key and self._seq else None

    def _write_checkpoint(self) -> dict:
        # TODO 2: sign the head of the chain.
        # Build {"seq", "head_hash", "signed_at" (UTC ISO)} and add "hmac": sign(self.hmac_key, f"{seq}:{head_hash}").
        # Append it to self.checkpoint_path the same way append() writes events. Return the dict.
        raise NotImplementedError("Lab 1: _write_checkpoint")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
