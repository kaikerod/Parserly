from __future__ import annotations

import re
from email.utils import parseaddr
from inspect import signature
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_LOCAL_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
_QUOTED_LOCAL = r'"(?:[\x20-\x21\x23-\x5B\x5D-\x7E]|\\[\x20-\x7E])*"'
_DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_DOMAIN_NAME = rf"(?:{_DOMAIN_LABEL}\.)+[A-Za-z]{{2,63}}"
_DOMAIN_LITERAL = r"\[(?:[\x21-\x5A\x5E-\x7E]|\\[\x20-\x7E])+\]"
_EMAIL_RE = re.compile(
    rf"^(?=.{{1,254}}$)(?:{_LOCAL_ATOM}(?:\.{_LOCAL_ATOM})*|{_QUOTED_LOCAL})@"
    rf"(?:{_DOMAIN_NAME}|{_DOMAIN_LITERAL})$"
)
_PARSEADDR_SUPPORTS_STRICT = "strict" in signature(parseaddr).parameters


def _parse_email_address(value: str) -> tuple[str, str]:
    if _PARSEADDR_SUPPORTS_STRICT:
        return parseaddr(value, strict=True)
    return parseaddr(value)


class RequestMagicLinkBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if not email or any(char in email for char in ("\r", "\n")):
            raise ValueError("invalid email address")

        _, parsed_email = _parse_email_address(email)
        if parsed_email != email or not _EMAIL_RE.fullmatch(email):
            raise ValueError("invalid email address")

        return email.lower()


class RequestMagicLinkResponse(BaseModel):
    message: str
    expires_in: int
    magic_link: str | None = None


class VerifyMagicLinkResponse(BaseModel):
    message: str
    user_id: UUID


class LogoutResponse(BaseModel):
    message: str
