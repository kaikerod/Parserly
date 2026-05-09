from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]],
        *,
        path_limits: dict[tuple[str, str], int],
    ) -> None:
        self.app = app
        self.path_limits = path_limits

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        max_body_bytes = self.path_limits.get((method, path))
        if max_body_bytes is None:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > max_body_bytes:
            await _send_payload_too_large(send, max_body_bytes)
            return

        total_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal total_bytes
            message = await receive()
            if message.get("type") != "http.request":
                return message

            body = message.get("body", b"")
            if isinstance(body, bytes):
                total_bytes += len(body)
                if total_bytes > max_body_bytes:
                    raise _RequestBodyTooLarge

            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await _send_payload_too_large(send, max_body_bytes)


class _RequestBodyTooLarge(Exception):
    pass


def _content_length(scope: dict[str, Any]) -> int | None:
    for raw_key, raw_value in scope.get("headers", []):
        if raw_key.lower() != b"content-length":
            continue
        try:
            return int(raw_value.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return None
    return None


async def _send_payload_too_large(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    max_body_bytes: int,
) -> None:
    body = json.dumps(
        {
            "detail": {
                "error": "payload_too_large",
                "message": "Request payload is too large.",
                "max_body_bytes": max_body_bytes,
            }
        },
        separators=(",", ":"),
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
