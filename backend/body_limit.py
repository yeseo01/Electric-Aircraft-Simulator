"""Bound multipart request bytes before the framework parses uploaded files."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from simulator.preview import MAX_UPLOAD_BYTES, PreviewValidationError


# File bytes have their own limit. Allow a small budget for multipart headers
# and fields as well, without allowing an unbounded request to reach the parser.
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024


class PreviewBodyLimitMiddleware:
    def __init__(
        self, app: ASGIApp, max_request_bytes: int = MAX_REQUEST_BYTES
    ) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != "/api/flight-previews"
        ):
            await self.app(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_request_bytes:
                error = PreviewValidationError(
                    "request_too_large",
                    "Multipart request exceeds the CSV size and form overhead budget.",
                )
                response = JSONResponse(
                    error.to_dict(),
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)
