"""
Telegram publisher.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from pipeline.http_client import get_default_session
from publishers.message_format import (
    build_conference_telegram_html,
    build_telegram_html_digest,
)


def _split_message(text: str, limit: int = 3500) -> List[str]:
    chunks: List[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def push_to_telegram(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
) -> None:
    telegram_cfg = config.get("telegram", {})
    bot_token = telegram_cfg.get("bot_token", "")
    chat_id = telegram_cfg.get("chat_id", "")
    if not bot_token or not chat_id or str(bot_token).startswith("YOUR_"):
        print("[Telegram] Missing bot_token or chat_id. Skip Telegram push.")
        return

    timeout = config.get("network", {}).get("request_timeout", 15)
    text = build_telegram_html_digest(papers, doc_url=doc_url)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for chunk in _split_message(text):
        resp = get_default_session().post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
    print("[Telegram] Digest push complete.")


def push_conference_to_telegram(summary: dict, config: dict) -> None:
    telegram_cfg = config.get("telegram", {})
    bot_token = telegram_cfg.get("bot_token", "")
    chat_id = telegram_cfg.get("chat_id", "")
    if not bot_token or not chat_id or str(bot_token).startswith("YOUR_"):
        print("[Telegram] Missing bot_token or chat_id. Skip Telegram conference push.")
        return

    timeout = config.get("network", {}).get("request_timeout", 15)
    text = build_conference_telegram_html(summary)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for chunk in _split_message(text):
        resp = get_default_session().post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
    print("[Telegram] Conference push complete.")
