"""Email notifications via Resend."""

from __future__ import annotations

import logging
from typing import Any

from condenseit.config import EmailConfig
from condenseit.store.secure_keys import SecureKeyStore

logger = logging.getLogger(__name__)


def send_digest_email(
    config: EmailConfig,
    key_store: SecureKeyStore,
    *,
    digest_md: str,
    digest_html: str,
    stats: dict[str, Any],
    digest_url: str = "",
) -> dict[str, str]:
    if not config.enabled:
        return {"status": "disabled_in_config", "reason": "email.enabled is false"}

    api_key = key_store.get_key("resend") or config.resend_api_key
    if not api_key:
        return {"status": "missing_credentials", "reason": "no resend api key"}

    try:
        import resend

        resend.api_key = api_key
        subject = f"CondenseIt digest: {stats.get('articles_count', 0)} articles"
        body = digest_md
        if digest_url:
            body += f"\n\nRead online: {digest_url}"

        params: resend.Emails.SendParams = {
            "from": config.from_address,
            "to": [config.to],
            "subject": subject,
            "html": digest_html,
            "text": body,
        }
        result = resend.Emails.send(params)
        return {"status": "sent", "id": str(result.get("id", ""))}
    except Exception as exc:
        logger.exception("Resend failed")
        return {"status": "error", "error": str(exc)}
