import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

READ_HEAVY_PREFIXES = (
    "/api/inventory/materials",
    "/api/auth/department-mappings",
    "/api/auth/department-contacts",
    "/api/dashboard/order-status",
    "/api/kpis",
    "/api/connectors/status",
    "/api/orders/summary",
)


class ETagCacheMiddleware(BaseHTTPMiddleware):
    """
    Computes ETag header and handles 304 Not Modified for read-heavy, rarely changing data.
    Sets standard Cache-Control headers to optimize client and proxy caching.
    """

    async def dispatch(self, request, call_next):
        if request.method != "GET":
            return await call_next(request)

        path = request.url.path
        is_cacheable = any(path.startswith(prefix) for prefix in READ_HEAVY_PREFIXES)

        response = await call_next(request)

        if not is_cacheable or response.status_code != 200:
            return response

        # Collect response bytes to calculate deterministic digest
        body = [chunk async for chunk in response.body_iterator]
        response_body = b"".join(body)

        etag = f'"{hashlib.md5(response_body).hexdigest()}"'
        if_none_match = request.headers.get("if-none-match")

        if if_none_match and if_none_match.strip("W/").strip('"') == etag.strip("W/").strip('"'):
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=60, must-revalidate",
                },
            )

        new_headers = dict(response.headers)
        new_headers["ETag"] = etag
        new_headers["Cache-Control"] = "public, max-age=60, must-revalidate"

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=new_headers,
            media_type=response.media_type,
        )
