from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar, Token
from uuid import uuid4

from fastapi import Request

_current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def set_current_trace_id(trace_id: str) -> Token[str | None]:
    return _current_trace_id.set(trace_id)


def reset_current_trace_id(token: Token[str | None]) -> None:
    _current_trace_id.reset(token)


def request_trace_id(request: Request) -> str:
    incoming_trace_id = request.headers.get("x-request-id")
    if incoming_trace_id:
        return incoming_trace_id[:128]

    return str(uuid4())


def log_structured(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    payload: dict[str, object] = {"event": event}
    trace_id = get_current_trace_id()
    if trace_id:
        payload["trace_id"] = trace_id

    payload.update({key: value for key, value in fields.items() if value is not None})
    logger.log(
        level,
        json.dumps(payload, ensure_ascii=True, default=str, separators=(",", ":")),
    )
