"""
Slack publisher.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from pipeline.http_client import get_default_session
from publishers.message_format import (
    build_conference_plaintext,
    build_conference_slack_blocks,
    build_plaintext_digest,
    build_slack_blocks,
)


def push_to_slack(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
) -> None:
    slack_cfg = config.get("slack", {})
    webhook_url = slack_cfg.get("webhook_url", "")
    if not webhook_url or str(webhook_url).startswith("YOUR_"):
        print("[Slack] Missing webhook_url. Skip Slack push.")
        return

    timeout = config.get("network", {}).get("request_timeout", 15)
    text = build_plaintext_digest(papers, doc_url=doc_url)
    blocks = build_slack_blocks(papers, doc_url=doc_url)
    resp = get_default_session().post(
        webhook_url,
        json={"text": text, "blocks": blocks},
        timeout=timeout,
    )
    resp.raise_for_status()
    print("[Slack] Digest push complete.")


def push_conference_to_slack(summary: dict, config: dict) -> None:
    slack_cfg = config.get("slack", {})
    webhook_url = slack_cfg.get("webhook_url", "")
    if not webhook_url or str(webhook_url).startswith("YOUR_"):
        print("[Slack] Missing webhook_url. Skip Slack conference push.")
        return

    timeout = config.get("network", {}).get("request_timeout", 15)
    text = build_conference_plaintext(summary)
    blocks = build_conference_slack_blocks(summary)
    resp = get_default_session().post(
        webhook_url,
        json={"text": text, "blocks": blocks},
        timeout=timeout,
    )
    resp.raise_for_status()
    print("[Slack] Conference push complete.")
