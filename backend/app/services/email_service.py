"""E-mail sending (aiosmtplib -> Mailpit locally) with an in-memory backend for tests, plus templates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

log = logging.getLogger("advar.email")


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class MemoryMailer:
    def __init__(self) -> None:
        self.outbox: list[Mail] = []

    async def send(self, mail: Mail) -> None:
        self.outbox.append(mail)

    def last_to(self, address: str) -> Mail | None:
        for m in reversed(self.outbox):
            if m.to.lower() == address.lower():
                return m
        return None


class SmtpMailer:
    async def send(self, mail: Mail) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = s.MAIL_FROM
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        for k, v in mail.headers.items():
            msg[k] = v
        msg.set_content(mail.text)
        if mail.html:
            msg.add_alternative(mail.html, subtype="html")
        try:
            await aiosmtplib.send(
                msg,
                hostname=s.SMTP_HOST,
                port=s.SMTP_PORT,
                username=s.SMTP_USER or None,
                password=s.SMTP_PASS or None,
                start_tls=s.SMTP_TLS,
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001 - mail must never break the request
            log.warning(
                "email send failed to=%s subject=%s error=%s", mail.to, mail.subject, exc.__class__.__name__
            )


_mailer: MemoryMailer | SmtpMailer | None = None


def get_mailer() -> MemoryMailer | SmtpMailer:
    global _mailer
    if _mailer is None:
        _mailer = MemoryMailer() if get_settings().MAIL_BACKEND == "memory" else SmtpMailer()
    return _mailer


def _app() -> str:
    return get_settings().APP_NAME


def _frontend(path: str) -> str:
    return get_settings().FRONTEND_URL.rstrip("/") + path


async def send_verification(to: str, token: str) -> None:
    link = _frontend(f"/verify-email?token={token}")
    text = f"Welcome to {_app()}.\n\nConfirm your e-mail by opening this link:\n{link}\n\nThe link is valid for 24 hours.\nVerification token: {token}\n"
    html = f'<p>Welcome to {_app()}.</p><p><a href="{link}">Confirm your e-mail</a> (valid for 24 hours).</p><p>Token: <code>{token}</code></p>'
    await get_mailer().send(
        Mail(
            to=to,
            subject=f"Confirm your {_app()} e-mail",
            text=text,
            html=html,
            headers={"X-ADVAR-Token": token, "X-ADVAR-Kind": "verify"},
        )
    )


async def send_password_reset(to: str, token: str) -> None:
    link = _frontend(f"/reset-password?token={token}")
    text = f"Reset your {_app()} password with this link (valid for 1 hour):\n{link}\n\nReset token: {token}\nIf you did not ask for this, ignore this e-mail.\n"
    await get_mailer().send(
        Mail(
            to=to,
            subject=f"Reset your {_app()} password",
            text=text,
            headers={"X-ADVAR-Token": token, "X-ADVAR-Kind": "reset"},
        )
    )


async def send_receipt(to: str, title: str, amount_display: str, method: str) -> None:
    text = f"Thank you. Your payment of {amount_display} ({method}) for the test '{title}' was received. The test is starting now.\n"
    await get_mailer().send(Mail(to=to, subject=f"{_app()} payment received", text=text))


async def send_manual_order(
    to: str, title: str, payment_code: str, local_display: str, expires_hours: int
) -> None:
    text = (
        f"Your order for the test '{title}' is waiting for payment.\n\nAmount: {local_display}\nPayment code: {payment_code}\n\n"
        f"Pay to one of our accounts shown in the app, then send the proof with the payment code to our social media page. "
        f"The order expires in {expires_hours} hours.\n"
    )
    await get_mailer().send(
        Mail(to=to, subject=f"{_app()} order {payment_code}: waiting for payment", text=text)
    )


async def send_manual_approved(to: str, title: str, payment_code: str) -> None:
    await get_mailer().send(
        Mail(
            to=to,
            subject=f"{_app()} order {payment_code} approved",
            text=f"Your payment for '{title}' was approved. The test is starting now.\n",
        )
    )


async def send_manual_cancelled(to: str, title: str, payment_code: str, reason: str) -> None:
    await get_mailer().send(
        Mail(
            to=to,
            subject=f"{_app()} order {payment_code} cancelled",
            text=f"Your order for '{title}' was cancelled.\nReason: {reason}\nYou can create a new order from the test page.\n",
        )
    )


async def send_report_ready(to: str, title: str, test_id: str, score: float | None) -> None:
    link = _frontend(f"/tests/{test_id}/report")
    text = (
        f"Your test '{title}' is complete"
        + (f" with a score of {score:.0f}/100" if score is not None else "")
        + f".\nOpen the report: {link}\n"
    )
    await get_mailer().send(Mail(to=to, subject=f"{_app()} report ready: {title}", text=text))


async def send_test_failed(to: str, title: str, test_id: str) -> None:
    link = _frontend(f"/tests/{test_id}")
    await get_mailer().send(
        Mail(
            to=to,
            subject=f"{_app()} test could not finish: {title}",
            text=f"Your test '{title}' could not finish. A free re-run is available: {link}\n",
        )
    )


async def send_admin_notice(to: str, subject: str, text: str) -> None:
    await get_mailer().send(Mail(to=to, subject=f"[{_app()} admin] {subject}", text=text))
