import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from gridmind.core.logging import new_request_id, request_id_ctx

logger = logging.getLogger("gridmind.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = new_request_id()
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            status = response.status_code if response is not None else 500
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                status,
                elapsed_ms,
            )
            if response is not None:
                response.headers["X-Request-Id"] = rid
            request_id_ctx.set("-")
