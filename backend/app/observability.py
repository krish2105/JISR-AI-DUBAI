"""
observability.py — Request IDs, JSON logs and model warm-up (Phase 14, DECISIONS P1).

- Every response carries `X-Request-ID` (the caller's, if it sent one, else a new one); with LOG_FORMAT=json each
  request is logged as one JSON line: method, path WITHOUT the query string (stream tokens travel there), status,
  duration, request id. Uvicorn's own access log is turned off in the container for the same reason.
- `warm_up()` loads the retrieval models before the first real request, so the first enquiry after a deploy is not
  the slow one; /health/ready reports when it is done.
"""

import json
import logging
import time
import uuid
from datetime import UTC, datetime

log = logging.getLogger("jisr.http")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": datetime.now(UTC).isoformat(), "level": record.levelname.lower(), "logger": record.name,
                   "msg": record.getMessage()}
        payload.update(getattr(record, "fields", {}) or {})
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(fmt: str) -> None:
    """LOG_FORMAT=json: one JSON object per line on stderr (what Fly and most log stores ingest)."""
    if fmt != "json":
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class RequestContext:
    """Pure ASGI middleware: request id header + one structured log line per request."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode()[:64]
        request_id = incoming if incoming.replace("-", "").isalnum() else uuid.uuid4().hex[:16]
        started = time.perf_counter()
        status = {"code": 500}

        async def send_with_id(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message = {**message, "headers": [*(message.get("headers") or []),
                                                  (b"x-request-id", request_id.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            if path not in ("/health", "/health/live", "/health/ready"):
                log.info("request", extra={"fields": {
                    "request_id": request_id, "method": scope.get("method"), "path": path,
                    "status": status["code"], "duration_ms": round((time.perf_counter() - started) * 1000, 1)}})


def warm_up_models() -> bool:
    """Load the embedding and reranker models with one tiny query (runs in a worker thread at start-up)."""
    from app.rag.index import index_exists

    if not index_exists():
        return False
    from app.rag.retriever import classify_hs, get_retriever

    classify_hs(get_retriever(), "brass lamps")
    return True
