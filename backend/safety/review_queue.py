"""Holds anything the gates flagged until a reviewer approves, edits, or
rejects it. In-memory for the hackathon; swap the storage without touching
the interface below if this needs to survive a restart later."""
import time
import uuid
from typing import Optional

from backend.safety.audit_log import AuditLog


class HumanReviewQueue:
    def __init__(self, audit_log: AuditLog):
        self._pending: dict[str, dict] = {}
        self._audit_log = audit_log

    def flag(self, query: str, mode: str, reason: str) -> dict:
        request_id = str(uuid.uuid4())
        self._pending[request_id] = {
            "id": request_id,
            "timestamp": time.time(),
            "query": query,
            "mode": mode,
            "reason": reason,
            "status": "PENDING",
            "reviewer_notes": None,
            "final_answer": None,
        }
        self._audit_log.log("ESCALATED_TO_HUMAN", f"{request_id}: {reason}")
        return {
            "status": "ESCALATED",
            "message": "This needs clinical verification before we can answer it. A reviewer has been notified.",
            "request_id": request_id,
        }

    def pending(self) -> list[dict]:
        return [r for r in self._pending.values() if r["status"] == "PENDING"]

    def resolve(self, request_id: str, action: str, notes: str = "",
                answer: Optional[str] = None) -> dict:
        if request_id not in self._pending:
            raise KeyError(f"no such request: {request_id}")
        entry = self._pending[request_id]
        entry["status"] = action.upper()
        entry["reviewer_notes"] = notes
        if action.upper() == "EDITED" and answer:
            entry["final_answer"] = answer
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
