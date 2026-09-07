"""Owner access protection for deployments of this personal dashboard."""

from secrets import compare_digest

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.config import get_settings

PUBLIC_PATHS = {"/api/health", "/api/access"}


class ApiAccessMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.token:
            return await self.app(scope, receive, send)
        if scope["method"] in {"GET", "HEAD"} and scope["path"] in PUBLIC_PATHS:
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        scheme, _, supplied = headers.get(b"authorization", b"").partition(b" ")
        if scheme.lower() != b"bearer" or not compare_digest(supplied, self.token):
            response = JSONResponse(
                {"detail": "Owner access is required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )
            return await response(scope, receive, send)

        async def private_response(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        return await self.app(scope, receive, private_response)


router = APIRouter(tags=["Access"])


@router.get("/access")
def access_status():
    return {"authentication_required": bool(get_settings().api_access_token.get_secret_value())}


@router.get("/access/check")
def check_access():
    return {"authenticated": True}
