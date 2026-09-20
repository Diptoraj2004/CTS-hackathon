"""Tamper-evident audit log. Each entry stores a hash of the entry before it
(same idea as a git commit chain), so editing anything after the fact breaks
the chain and verify() catches it. No blockchain needed for that property.

Persisted to data/audit/audit_log.json (atomic write, same pattern as
ingest_jobs.py) — previously pure in-memory, meaning a restart silently
reset the chain to empty and it still reported "valid" (an empty chain is
trivially unbroken), which is exactly the failure mode a tamper-evident log
is supposed to catch, not produce.

Right-to-erasure note: a hash chain can't support editing or deleting a past
entry without registering as tampering — that's the whole point of it. So
"delete a user's data but keep the audit trail" only works if raw PII never
enters the log in the first place. log() redacts `details` itself, on top of
whatever the caller already redacted, so this can't be forgotten at a call site.
"""
import hashlib
import json
import time
from pathlib import Path

from backend.safety.redaction import redact

LOG_PATH = Path("data/audit/audit_log.json")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class AuditLog:
    def __init__(self):
        self._chain: list[dict] = self._load()
        if not self._chain:
            self._append("SYSTEM_INIT", "audit log started", "0")

    def _load(self) -> list[dict]:
        if LOG_PATH.exists():
            try:
                return json.loads(LOG_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[audit_log] couldn't read existing log ({type(e).__name__}: {e}); starting a fresh one")
        return []

    def _save(self) -> None:
        tmp = LOG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._chain), encoding="utf-8")
        tmp.replace(LOG_PATH)

    def _hash(self, entry: dict) -> str:
        return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()

    def _append(self, event_type: str, details: str, previous_hash: str, ip: str | None = None) -> dict:
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
            "ip": ip,
            "previous_hash": previous_hash,
        }
        entry["hash"] = self._hash(entry)
        self._chain.append(entry)
        self._save()
        return entry

    def log(self, event_type: str, details: str, ip: str | None = None) -> dict:
        return self._append(event_type, redact(details), self._chain[-1]["hash"], ip=ip)

    def verify(self) -> tuple[bool, str]:
        for i in range(1, len(self._chain)):
            prev, cur = self._chain[i - 1], self._chain[i]
            if cur["previous_hash"] != prev["hash"]:
                return False, f"broken link at entry {i}"
            recomputed = self._hash({k: v for k, v in cur.items() if k != "hash"})
            if recomputed != cur["hash"]:
                return False, f"entry {i} was altered after being written"
        return True, "chain intact"

    def entries(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Most-recent-first page of the chain, for the audit-log listing
        endpoint the admin UI actually needs (verify() alone only gives
        counts, never the entries themselves)."""
        return list(reversed(self._chain))[offset:offset + limit]

    def __len__(self) -> int:
        return len(self._chain)


if __name__ == "__main__":
    log = AuditLog()
    log.log("MODE_MISMATCH_ESCALATION", "patient mode asked a clinician-level question")
    log.log("QUERY_ANSWERED", "session=demo")
    ok, msg = log.verify()
    print(f"before tampering: {ok}, {msg}")

    log._chain[1]["details"] = "tampered"  # simulate someone editing history
    ok, msg = log.verify()
    print(f"after tampering:  {ok}, {msg}")
