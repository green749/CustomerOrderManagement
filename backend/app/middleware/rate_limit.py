import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from ..config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Tracks timestamp lists: requests[client_ip + route_type] = [ts1, ts2, ...]
        self._requests = defaultdict(list)

    def _clean_old_requests(self, key: str, window_sec: int, now: float):
        cutoff = now - window_sec
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Rate limit checks for specific sensitive endpoints
        path = request.url.path.lower()
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        limit = None
        window = 60
        route_type = None

        if "/api/auth/login" in path and request.method == "POST":
            limit = settings.rate_limit_login_max
            window = settings.rate_limit_login_window_sec
            route_type = "login"
        elif "/api/agent/chat" in path and request.method == "POST":
            limit = settings.rate_limit_ai_max
            window = settings.rate_limit_ai_window_sec
            route_type = "ai"
        elif any(path.startswith(p) for p in ["/api/connectors/test", "/api/connectors/connect", "/api/connectors/seed", "/api/connectors/sync"]) and request.method == "POST":
            limit = 20  # Max 20 connector actions per minute
            window = 60
            route_type = "connectors"

        if limit and route_type:
            key = f"{client_ip}:{route_type}"
            self._clean_old_requests(key, window, now)

            if len(self._requests[key]) >= limit:
                retry_after = int(window - (now - self._requests[key][0])) + 1
                req_id = getattr(request.state, "request_id", None)
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": f"Rate limit exceeded for {route_type}. Please try again later.",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "request_id": req_id,
                    },
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            self._requests[key].append(now)

        return await call_next(request)

