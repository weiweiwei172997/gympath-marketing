"""Bound requests before parsing and apply browser protections to every response."""

import asyncio
import json
import logging
import os
from threading import Lock
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from .auth import AuthRateLimiter


MAX_BODY_BYTES = 4096
BODY_TIMEOUT_SECONDS = 10
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; connect-src 'self'; base-uri 'none'; "
    "object-src 'none'; frame-ancestors 'none'; form-action 'none'"
)
api_rate_limiter = AuthRateLimiter(limit=120, window_seconds=60)
logger = logging.getLogger("gympath.security")


class RequestBudget:
    """Reject excess work instead of queueing unlimited password hashes/plans."""

    def __init__(self):
        self.limits = {"auth": 2, "api": 8}
        self.active = {key: 0 for key in self.limits}
        self.lock = Lock()

    def acquire(self, kind):
        with self.lock:
            if self.active[kind] >= self.limits[kind]:
                return False
            self.active[kind] += 1
            return True

    def release(self, kind):
        with self.lock:
            self.active[kind] -= 1


request_budget = RequestBudget()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def _valid_host(headers):
    values = [value.decode("latin-1") for key, value in headers if key == b"host"]
    if len(values) != 1:
        return False
    host = values[0]
    if not host or any(char in host for char in " /\\@#?\r\n\t"):
        return False
    try:
        parsed = urlsplit("http://" + host)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
        if not hostname or (port is not None and not 1 <= port <= 65535):
            return False
        hostname.encode("ascii")
    except (ValueError, UnicodeError):
        return False
    # Portable local/source copies accept syntactically valid hosts. A public
    # deployment sets its exact host list before importing the application.
    allowed = {item.strip().lower() for item in os.environ.get("GYMPATH_ALLOWED_HOSTS", "").split(",") if item.strip()}
    return not allowed or hostname in allowed


class SecurityMiddleware:
    """Pure ASGI avoids unbounded request-body buffering in framework middleware."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False
        budget_kind = None
        path = scope.get("path", "")
        is_api = path.startswith("/api/")

        def release_budget():
            nonlocal budget_kind
            if budget_kind is not None:
                request_budget.release(budget_kind)
                budget_kind = None

        async def secured_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                protections = {
                    b"content-security-policy": CONTENT_SECURITY_POLICY.encode("ascii"),
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"same-origin",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                    b"cross-origin-opener-policy": b"same-origin",
                    b"cross-origin-resource-policy": b"same-origin",
                }
                if is_api:
                    protections[b"cache-control"] = b"no-store"
                if scope.get("scheme") == "https":
                    protections[b"strict-transport-security"] = b"max-age=31536000"
                message = dict(message)
                message["headers"] = [(key, value) for key, value in message.get("headers", []) if key.lower() not in protections] + list(protections.items())
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                # WSGI adapters may finish/cancel the ASGI task as soon as the
                # final body is sent. Release completed work before that point.
                release_budget()
            await send(message)

        async def reject(status, detail, retry=None):
            headers = {"Retry-After": str(retry)} if retry else None
            content = {"detail": detail}
            if status == 422:
                content["errors"] = [{"field": "body", "message": detail, "code": "json_invalid"}]
            await JSONResponse(content, status_code=status, headers=headers)(scope, receive, secured_send)

        headers = scope.get("headers", [])
        if not _valid_host(headers):
            await reject(400, "请求地址不正确。")
            return
        if not is_api:
            await self.app(scope, receive, secured_send)
            return
        origins = [value for key, value in headers if key == b"origin"]
        if len(origins) > 1:
            await reject(400, "请求格式不正确。")
            return
        lengths = [value for key, value in headers if key == b"content-length"]
        if lengths:
            if len(lengths) != 1:
                await reject(400, "请求格式不正确。")
                return
            length_value = lengths[0].strip()
            if not length_value.isdigit():
                await reject(400, "请求格式不正确。")
                return
            elif len(length_value) > 10 or int(length_value) > MAX_BODY_BYTES:
                await reject(413, "请求内容过大，请缩短后重试。")
                return
        encodings = [value.lower() for key, value in headers if key == b"content-encoding"]
        if encodings and encodings != [b"identity"]:
            await reject(415, "请使用 JSON 格式提交。")
            return
        is_auth = scope["method"] == "POST" and path in {"/api/auth/register", "/api/auth/login"}
        if not is_auth:
            address = scope.get("client", ("unknown", 0))
            if not api_rate_limiter.allow(address[0] if address else "unknown"):
                await reject(429, "操作过于频繁，请稍后再试。", 60)
                return
        chunks = []
        size = 0
        async def read_body():
            nonlocal size
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return False
                body = message.get("body", b"")
                size += len(body)
                if size > MAX_BODY_BYTES:
                    await reject(413, "请求内容过大，请缩短后重试。")
                    return False
                chunks.append(body)
                if not message.get("more_body", False):
                    return True

        try:
            if not await asyncio.wait_for(read_body(), timeout=BODY_TIMEOUT_SECONDS):
                return
        except asyncio.TimeoutError:
            await reject(408, "请求超时，请重试。")
            return
        body = b"".join(chunks)
        if body:
            content_types = [value.decode("latin-1").split(";", 1)[0].strip().lower() for key, value in headers if key == b"content-type"]
            if len(content_types) != 1 or not (content_types[0] == "application/json" or (content_types[0].startswith("application/") and content_types[0].endswith("+json"))):
                await reject(415, "请使用 JSON 格式提交。")
                return
            try:
                json.loads(body, object_pairs_hook=_unique_object)
            except (ValueError, RecursionError):
                await reject(422, "请求格式不正确，请检查填写内容。")
                return
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        kind = "auth" if is_auth else "api"
        if not request_budget.acquire(kind):
            await reject(503, "服务暂时繁忙，请稍后重试。", 5)
            return
        budget_kind = kind
        try:
            await self.app(scope, replay, secured_send)
        except Exception as error:
            # Keep bodies, credentials, cookies and database paths out of logs
            # and browser error responses. Do not create a second response.
            logger.error("Backend request failed (%s)", type(error).__name__)
            if started:
                raise
            await reject(500, "服务暂时不可用，请稍后重试。")
        finally:
            release_budget()
