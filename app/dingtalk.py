from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any

import requests

from .config import Settings

logger = logging.getLogger(__name__)


def _signed_url(settings: Settings) -> str:
    settings.require_dingtalk()
    webhook = settings.dingtalk_webhook
    if not settings.dingtalk_secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{settings.dingtalk_secret}"
    hmac_code = hmac.new(
        settings.dingtalk_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def send_markdown(settings: Settings, title: str, markdown_text: str, retries: int = 3, interval_seconds: int = 10) -> dict[str, Any]:
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": markdown_text},
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(_signed_url(settings), json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("errcode") not in (0, None):
                raise RuntimeError(f"DingTalk API error: {data}")
            return data
        except Exception as exc:  # pragma: no cover - network behavior
            last_error = exc
            logger.warning("DingTalk push failed on attempt %s/%s: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(interval_seconds)
    raise RuntimeError(f"DingTalk push failed after {retries} attempts: {last_error}")
