"""Minimal admin auth: a shared secret in a header, checked on every
mutating or internal-facing route (/ingest, document delete, review
resolution, audit/dashboard reads, session erasure). Not a user/role system
— that needs a product decision (who are the roles, where do accounts live)
that isn't a code fix. This is the difference between "anyone on the
internet can call /ingest" and "you need the admin key," which is the gap
that actually matters for a demo.

ADMIN_API_KEY must be set in the environment. If it isn't, every admin
route fails closed (403) rather than silently allowing everything — a
missing secret should never mean "no auth," it should mean "no access."
"""
import hashlib
import os

from fastapi import Header, HTTPException

_configured_key = os.getenv("ADMIN_API_KEY")

if not _configured_key:
    print("[auth] WARNING: ADMIN_API_KEY is not set — every admin-only "
          "endpoint will reject all requests (fail closed) until it is. "
          "Set it in your .env or Colab environment before demoing the "
          "admin/upload flows.")


def _constant_time_eq(a: str, b: str) -> bool:
    return hashlib.sha256(a.encode()).digest() == hashlib.sha256(b.encode()).digest()


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency — add `Depends(require_admin_key)` to any route
    that should require the admin key. Raises 401/403 rather than returning
    a value; routes that use it don't need to do anything with the result."""
    if not _configured_key:
        raise HTTPException(status_code=503, detail="Admin auth is not configured on this server.")
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key header.")
    if not _constant_time_eq(x_admin_key, _configured_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")
