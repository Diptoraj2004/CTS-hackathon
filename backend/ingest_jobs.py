"""Background job tracking for /ingest.

The old /ingest handler ran parse -> scan -> embed -> store synchronously
inside one HTTP request. For a real PDF (OCR fallback, a cold embedding
model on first load) that's 30s+ held open across a Colab/ngrok tunnel --
exactly the shape of thing that comes back as a timeout / 500, and if the
admin reloads the page mid-request the browser drops the connection and
every bit of progress info in React state goes with it.

This module gives each upload a job_id and a checkpoint file on disk
(data/uploads/_jobs/{job_id}.json), written atomically at every stage
transition. The actual pipeline runs on a background thread (see
_run_ingestion in main.py) so the HTTP request returns almost immediately
with just the job_id. The frontend polls GET /ingest/{job_id}/status
instead of holding one long request open -- a reload just means "start
polling the same job_id again," not "lose everything."

Note on restarts: if the backend process itself dies mid-job, the
checkpoint file still reports the last stage reached, but the background
thread doing the actual work is gone with the process, so the job won't
silently finish on its own -- it needs re-submitting. That's a real,
disclosed limit, not a full resume-from-crash system; a hackathon-scale
in-memory + checkpoint-file setup can't do more than that without a real
job queue (Celery/RQ), which isn't worth the build risk this week.
"""
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

JOBS_DIR = Path("data/uploads/_jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_jobs: dict[str, dict] = {}  # in-memory cache; source of truth while the process is alive


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _write_checkpoint(job: dict) -> None:
    """Write-to-temp-then-rename so a crash mid-write never leaves a
    half-written, unparseable checkpoint file behind."""
    path = _job_path(job["job_id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job), encoding="utf-8")
    tmp.replace(path)


def create_job(filename: str, drug_name: str, doc_id: Optional[str]) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "filename": filename,
        "drug_name": drug_name,
        "doc_id": doc_id,
        "stage": "QUEUED",       # QUEUED -> PARSING -> SCANNING -> EMBEDDING -> STORED | REJECTED | FAILED
        "detail": "Waiting to start.",
        "chunks_found": None,
        "chunks_stored": None,
        "error": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with _lock:
        _jobs[job_id] = job
    _write_checkpoint(job)
    return dict(job)


def update_job(job_id: str, **fields) -> dict:
    with _lock:
        job = _jobs.get(job_id) or get_job(job_id) or {"job_id": job_id}
        job.update(fields)
        job["updated_at"] = time.time()
        _jobs[job_id] = job
        _write_checkpoint(job)
        return dict(job)


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        if job_id in _jobs:
            return dict(_jobs[job_id])
    path = _job_path(job_id)
    if path.exists():
        job = json.loads(path.read_text(encoding="utf-8"))
        with _lock:
            _jobs[job_id] = job
        return dict(job)
    return None
