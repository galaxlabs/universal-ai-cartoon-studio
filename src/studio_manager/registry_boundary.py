"""Pre-parser protection for registry HTTP requests, not a global upload policy."""

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from studio_manager.auth import require_api_token

REGISTRY_MAX_BODY_BYTES = 1024 * 1024
PREFIXES = ("/api/v1/agents", "/api/v1/skills")


class RegistryRequestBoundary:
    def __init__(self, app: ASGIApp, max_body_bytes: int = REGISTRY_MAX_BODY_BYTES):
        if max_body_bytes <= 0:
            raise ValueError("registry request body limit must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str, headers=None) -> None:
        response = JSONResponse(
            {"detail": detail}, status_code=status,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", **(headers or {})},
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        root_path = scope.get("root_path", "")
        # Match the router's segment-aware ASGI mount/root-path semantics.
        if root_path and path.startswith(root_path):
            if path == root_path:
                path = ""
            elif path[len(root_path):len(root_path) + 1] == "/":
                path = path[len(root_path):]
        if scope["type"] != "http" or not any(path == prefix or path.startswith(prefix + "/") for prefix in PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        credentials = headers.getlist("authorization")
        try:
            # Reuse the existing H1 verifier, using only headers/app state. No
            # Request.body/json/form call or receive invocation occurs here.
            require_api_token(Request(scope), credentials[0] if len(credentials) == 1 else None)
        except HTTPException as exc:
            await self.reject(scope, receive, send, exc.status_code, str(exc.detail), exc.headers)
            return

        lengths = headers.getlist("content-length")
        if len(lengths) > 1 or (lengths and headers.getlist("transfer-encoding")):
            await self.reject(scope, receive, send, 400, "ambiguous request body framing")
            return
        declared = None
        if lengths:
            raw = lengths[0].strip(" \t")  # HTTP OWS only, not arbitrary Unicode whitespace.
            if not raw or not raw.isascii() or not raw.isdigit():
                await self.reject(scope, receive, send, 400, "invalid Content-Length")
                return
            digits = raw.lstrip("0") or "0"
            # Compare lengths before int conversion: huge header integers must
            # not trigger unbounded conversion or Python's integer-digit error.
            maximum = str(self.max_body_bytes)
            if len(digits) > len(maximum) or (len(digits) == len(maximum) and digits > maximum):
                await self.reject(scope, receive, send, 413, "registry request body exceeds configured limit")
                return
            declared = int(digits)

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self.reject(scope, receive, send, 400, "incomplete request body stream")
                return
            chunk = message.get("body", b"")
            if len(chunk) > self.max_body_bytes - len(body):
                # Do not append the overflowing chunk, parse anything, drain the
                # rest of the stream, or call the application/router.
                await self.reject(scope, receive, send, 413, "registry request body exceeds configured limit")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if declared is not None and declared != len(body):
            await self.reject(scope, receive, send, 400, "request body length does not match Content-Length")
            return

        payload = bytes(body)
        del body
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
