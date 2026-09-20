"""Holds anything the gates flagged until a reviewer approves, edits, or
rejects it. Persisted to data/audit/review_queue.json (previously pure
in-memory — a restart silently lost every pending review with no trace)."""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from backend.safety.audit_log import AuditLog
from backend.safety.redaction import redact

QUEUE_PATH = Path("data/audit/review_queue.json")
QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)


class HumanReviewQueue:
    def __init__(self, audit_log: AuditLog):
        self._pending: dict[str, dict] = self._load()
        self._audit_log = audit_log

    def _load(self) -> dict[str, dict]:
        if QUEUE_PATH.exists():
            try:
                return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[review_queue] couldn't read existing queue ({type(e).__name__}: {e}); starting empty")
        return {}

    def _save(self) -> None:
        tmp = QUEUE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._pending), encoding="utf-8")
        tmp.replace(QUEUE_PATH)

    def flag(self, query: str, mode: str, reason: str) -> dict:
        request_id = str(uuid.uuid4())
        self._pending[request_id] = {
            "id": request_id,
            "timestamp": time.time(),
            "query": redact(query),  # this now persists to disk — don't keep raw PII there
            "mode": mode,
            "reason": reason,
            "status": "PENDING",
            "reviewer_notes": None,
            "final_answer": None,
        }
        self._save()
        self._audit_log.log("ESCALATED_TO_HUMAN", f"{request_id}: {reason}")
        return {
            "status": "ESCALATED",
            "message": "This needs clinical verification before we can answer it. A reviewer has been notified.",
            "request_id": request_id,
        }

    def pending(self) -> list[dict]:
        return [r for r in self._pending.values() if r["status"] == "PENDING"]

    def get(self, request_id: str) -> dict:
        if request_id not in self._pending:
            raise KeyError(f"no such request: {request_id}")
        return self._pending[request_id]

    def resolve(self, request_id: str, action: str, notes: str = "",
                answer: Optional[str] = None) -> dict:
        if request_id not in self._pending:
            raise KeyError(f"no such request: {request_id}")
        entry = self._pending[request_id]
        entry["status"] = action.upper()
        entry["reviewer_notes"] = notes
        if action.upper() == "EDITED" and answer:
            entry["final_answer"] = answer
        self._save()
        self._audit_log.log(f"HUMAN_REVIEW_{action.upper()}", f"{request_id}: {notes}")
        return entry


if __name__ == "__main__":
    log = AuditLog()
    q = HumanReviewQueue(log)
    result = q.flag("Infant dosage for 6kg?", "patient", "mode mismatch")
    print(result["message"])
    pending = q.pending()
    q.resolve(pending[0]["id"], "reject", "cannot give pediatric dosing to patients directly")
    print(f"pending after resolve: {len(q.pending())}")
