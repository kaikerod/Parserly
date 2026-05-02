from __future__ import annotations

import asyncio
from html import escape

from app.core.config import Settings


class EmailDeliveryError(Exception):
    pass


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_magic_link(
        self,
        *,
        email: str,
        magic_link: str,
        expires_in: int,
    ) -> None:
        if not self.settings.resend_api_key:
            if self.settings.environment == "production":
                raise EmailDeliveryError("Resend API key is not configured.")
            return

        if not self.settings.email_from or self.settings.email_from == "noreply@localhost":
            raise EmailDeliveryError("Sender email is not configured.")

        try:
            import resend
        except ModuleNotFoundError as exc:
            raise EmailDeliveryError("Resend SDK is not installed.") from exc

        resend.api_key = self.settings.resend_api_key
        params: dict[str, object] = {
            "from": self.settings.email_from,
            "to": [email],
            "subject": "Seu link de acesso ao Parserly",
            "html": self._build_magic_link_html(magic_link=magic_link, expires_in=expires_in),
            "text": self._build_magic_link_text(magic_link=magic_link, expires_in=expires_in),
        }

        try:
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as exc:
            raise EmailDeliveryError("Could not send magic link email.") from exc

    @staticmethod
    def _build_magic_link_html(*, magic_link: str, expires_in: int) -> str:
        safe_magic_link = escape(magic_link, quote=True)
        minutes = max(expires_in // 60, 1)

        return f"""
        <div style="font-family: Arial, sans-serif; color: #17202a; line-height: 1.6;">
          <h1 style="font-size: 22px; margin: 0 0 16px;">Acesse sua conta Parserly</h1>
          <p style="margin: 0 0 20px;">
            Use o botao abaixo para entrar com seguranca. O link expira em {minutes} minutos
            e so pode ser usado uma vez.
          </p>
          <p style="margin: 0 0 24px;">
            <a
              href="{safe_magic_link}"
              style="background: #45ff73; border-radius: 6px; color: #111827; display: inline-block; font-weight: 700; padding: 12px 18px; text-decoration: none;"
            >
              Entrar no Parserly
            </a>
          </p>
          <p style="font-size: 13px; margin: 0 0 8px; color: #52616f;">
            Se o botao nao funcionar, copie e cole este endereco no navegador:
          </p>
          <p style="font-size: 13px; margin: 0; word-break: break-all;">
            <a href="{safe_magic_link}" style="color: #3454d1;">{safe_magic_link}</a>
          </p>
        </div>
        """

    @staticmethod
    def _build_magic_link_text(*, magic_link: str, expires_in: int) -> str:
        minutes = max(expires_in // 60, 1)
        return (
            "Acesse sua conta Parserly\n\n"
            f"Use este link para entrar: {magic_link}\n\n"
            f"O link expira em {minutes} minutos e so pode ser usado uma vez."
        )
