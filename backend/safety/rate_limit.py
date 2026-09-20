"""Basic app-layer abuse protection: caps requests per IP per minute.

Honest scope note: this is not DDoS protection. A real volumetric attack
needs infrastructure-level mitigation (a WAF/CDN in front of the app —
Cloudflare, etc.), which is outside what an app process can defend against
by itself. What this actually does: stops one client from hammering the
LLM/embedding calls and running up cost or starving other users, which is
the realistic risk for a hackathon demo, not a botnet."""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 30

# Status polling is a cheap dict lookup, not an LLM/embedding call — the
# thing the limit exists to protect against. At 1.2s poll interval a single
# upload over ~36s already blows the shared 30/min budget and starts 429ing
# a user watching their own upload progress.
_EXEMPT_PREFIXES = ("/ingest/", )
_EXEMPT_SUFFIXES = ("/status",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(_EXEMPT_PREFIXES) and path.endswith(_EXEMPT_SUFFIXES):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        hits = self._hits[client_ip]

        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= MAX_REQUESTS_PER_WINDOW:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
            )

        hits.append(now)
        return await call_next(request)
