from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateChargeResponse(BaseModel):
    billing_id: str
    pix_qr_code: str
    pix_copy_paste: str
    expires_at: datetime
    expires_in: int
    amount_cents: int


class WebhookResponse(BaseModel):
    received: bool
    status: str
