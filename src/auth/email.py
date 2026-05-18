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
    threading.Thread(target=lambda: send_email_sync(to, subject, html), daemon=True).start()


def send_email_sync(to: str, subject: str, html: str) -> bool:
    """Synchronous send — returns True if sent, False if skipped or failed."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("email_not_configured — skipping send to %s", to)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.smtp_from
        msg["To"]      = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.smtp_from, to, msg.as_string())
        logger.info("email_sent to=%s subject=%s", to, subject)
        return True
    except Exception:
        logger.exception("email_send_failed to=%s", to)
        return False
