"""Tamper-evident audit log. Each entry stores a hash of the entry before it
(same idea as a git commit chain), so editing anything after the fact breaks
the chain and verify() catches it. No blockchain needed for that property."""
import hashlib
import json
import time


class AuditLog:
    def __init__(self):
        self._chain: list[dict] = []
        self._append("SYSTEM_INIT", "audit log started", "0")

    def _hash(self, entry: dict) -> str:
        return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()

    def _append(self, event_type: str, details: str, previous_hash: str) -> dict:
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
            "previous_hash": previous_hash,
        }
        entry["hash"] = self._hash(entry)
        self._chain.append(entry)
        return entry

    def log(self, event_type: str, details: str) -> dict:
        return self._append(event_type, details, self._chain[-1]["hash"])

    def verify(self) -> tuple[bool, str]:
        for i in range(1, len(self._chain)):
            prev, cur = self._chain[i - 1], self._chain[i]
            if cur["previous_hash"] != prev["hash"]:
                return False, f"broken link at entry {i}"
            recomputed = self._hash({k: v for k, v in cur.items() if k != "hash"})
            if recomputed != cur["hash"]:
                return False, f"entry {i} was altered after being written"
        return True, "chain intact"

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
