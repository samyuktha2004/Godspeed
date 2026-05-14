"""Fire-and-forget email sender using stdlib smtplib (no extra packages required)."""

import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import settings
import logging

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> None:
    """Fire-and-forget — logs on failure, never raises."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("email_not_configured — skipping send to %s", to)
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from
            msg["To"] = to
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
                s.starttls()
                s.login(settings.smtp_user, settings.smtp_password)
                s.sendmail(settings.smtp_from, to, msg.as_string())
            logger.info("email_sent to=%s subject=%s", to, subject)
        except Exception:
            logger.exception("email_send_failed to=%s", to)

    threading.Thread(target=_send, daemon=True).start()
