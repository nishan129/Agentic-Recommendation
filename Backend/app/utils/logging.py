"""
Structured logging setup and a request-logging middleware.

Never logs passwords, JWTs, API keys, or other sensitive payload data -
only request metadata (method, path, status, duration, user id when known).
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.request")


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Quiet down noisy third-party loggers unless we're debugging.
    if not debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request_id=%s method=%s path=%s status=ERROR duration_ms=%s",
                request_id, request.method, request.url.path, duration_ms,
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        user_id = getattr(request.state, "user_id", None)
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s user_id=%s",
            request_id, request.method, request.url.path,
            response.status_code, duration_ms, user_id or "-",
        )
        response.headers["X-Request-ID"] = request_id
        return response