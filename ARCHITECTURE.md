# DrugDocQA — Technical Architecture & Stack

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python), uvicorn |
| Frontend | React + TypeScript + Vite, React Router |
| Vector store | LanceDB (embedded, file-based) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Generation | Groq API (primary) → Ollama (local fallback) |
| Parsing | PyMuPDF (PDF), lxml (SPL XML), pytesseract (OCR fallback) |
| PII/PHI redaction | Microsoft Presidio + spaCy (`en_core_web_sm`) |
| Auth | Custom: SQLite users, scrypt password hashing, HMAC-signed bearer tokens, Google OAuth |
| Session memory | LangChain message objects, persisted to SQLite |
| Persistent state | SQLite (auth, sessions, rate limits, analytics) + append-only JSONL (audit log) + JSON (review queue, ingest jobs) |
| Rate limiting | Custom middleware, SQLite-backed |
| Orchestration | Plain Python — no LangChain agent framework in the query path (LangChain used only for chat memory objects) |

## 2. Query pipeline

```
POST /query
  → injection scan (raw query text) → reject if flagged
  → mode-consistency gate (patient asking clinician-level Q?) → escalate (high risk)
  → chat-memory check: near-exact repeat of last question? → return cached answer, skip retrieval
  → pipeline.answer():
      understand() — drug extraction (+ brand→generic aliasing), follow-up
                      resolution from session history, section-hint detection
      → retrieve() — vector search, filtered by drug name + section hints
      → injection scan (retrieved chunks) → escalate (high risk) if flagged
      → relevance gate — enough evidence? right drug? → escalate (risk: none
        if off-topic / no drug identified, low if a real drug question with
        weak evidence)
      → generate() — Groq, falls back to Ollama on failure
      → redact() — PII/PHI removed BEFORE citation processing, fails closed
      → citation processing — validates every claim traces to a retrieved
        chunk, computes citation coverage
      → confidence calibration → bucket (low/medium/high)
  → APPROVED → answer + citations returned
  → ESCALATED → human review queue entry (skipped for off-topic questions)
```

## 3. Ingestion pipeline

```
POST /ingest (auth: admin bearer token)
  → file written to permanent path immediately (job-id-prefixed, collision-safe)
  → submitted to a bounded thread pool (3 workers) — request returns a job_id
    right away, doesn't block on parsing/embedding
  → parse + chunk (PDF/XML, OCR fallback)
  → 0 extractable chunks → FAILED (was silently "stored" before)
  → injection scan on every chunk → any flagged → REJECTED, nothing stored
  → embed + write to LanceDB (atomic upsert where supported)
  → only now: register document version/metadata (after storage succeeds,
    not before — a failed/rejected doc no longer leaves a phantom record)
  → known-drug list cache invalidated so the new drug is queryable immediately
GET /ingest/{job_id}/status — poll for progress (exempt from rate limiting)
```

## 4. Auth

- Email/password: scrypt-hashed, stored in SQLite, HMAC-signed bearer tokens (1hr TTL)
- Google OAuth: state-token CSRF protection, links to existing account by email or creates one
- Admin role: bootstrapped via `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars on startup, or promoted manually
- Frontend stores the bearer token in `sessionStorage` (cleared on tab close/logout)
- `/admin/*` routes are guarded client-side (redirect if no token) and every admin API call is enforced server-side regardless (`Depends(require_admin_key)` — despite the name, checks the bearer token + admin role, not a shared key)

## 5. Safety spine

- **Redaction**: fails closed — if the model isn't available, escalates rather than serving unprotected text
- **Injection defense**: scans the live query, retrieved chunks, and every ingested chunk before storage; explicit `<context>`/`<instructions>` delimiting in the LLM prompt
- **Audit log**: hash-chained (tamper-evident), append-only JSONL, thread-safe
- **Review queue**: disk-persisted, thread-safe; off-topic questions don't enter it
- **Right-to-erasure**: `DELETE /session/{id}` clears chat memory (audit log is untouched by design — it's built to never hold raw PII in the first place)

## 6. Known open gaps

Two LanceDB wrapper implementations still coexist (one unused for the live path). PDF section/version/date extraction is still heuristic, not fully reliable on arbitrary layouts. No confidence-bucket calibration against real reviewed data yet (thresholds are a documented placeholder — see `confidence.py`). Frontend dashboard's historical activity chart and source-type breakdown are still static — no backend history tracking for those specific views yet (`/dashboard/stats` covers live counts only). No dependency version pinning across all requirements files. SQLite-backed state (auth, sessions, rate limits) lives under `data/`, which is wiped on a fresh Colab instance unless that directory is persisted elsewhere.

## Intent-Orchestrated Retrieval (September 2026)

The query path now starts with a lightweight intent classifier before vector retrieval. This avoids unnecessary retrieval for history-only questions and selects FAERS for frequency/report-count queries:

`query -> intent router -> history / label retrieval / FAERS -> generation -> citation validation -> quality metrics`

The API exposes `intent`, `retrieval_used`, `history_used`, `faers_used`, and `quality_metrics` on each response. Live quality metrics are explicitly estimates; the gold-set evaluator remains authoritative for benchmark reporting.
