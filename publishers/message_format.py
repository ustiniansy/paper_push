"""
Shared message rendering for chat-style publishers.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Dict, Iterable, List, Optional


def build_plaintext_digest(papers: Iterable[Dict], doc_url: Optional[str] = None) -> str:
    papers = list(papers)
    date_str = datetime.now().strftime("%Y-%m-%d")
    if not papers:
        return f"{date_str} Daily Paper Report\n\nNo selected papers in this run."

    lines: List[str] = [f"{date_str} Daily Paper Report", "", f"Selected papers: {len(papers)}", ""]
    for index, paper in enumerate(papers, 1):
        lines.append(f"{index}. {paper['title']}")
        lines.append(f"   Score: {paper.get('score', 0)}/10")
        lines.append(f"   Source: {paper.get('source', 'arxiv')}")
        lines.append(f"   URL: {paper.get('url', '')}")
        if paper.get("code_url"):
            lines.append(f"   Code: {paper['code_url']}")
        if paper.get("score_reason"):
            lines.append(f"   Why selected: {paper['score_reason']}")
        lines.append("")
    if doc_url:
        lines.extend(["Feishu doc:", doc_url, ""])
    return "\n".join(lines).strip()


def build_telegram_html_digest(papers: Iterable[Dict], doc_url: Optional[str] = None) -> str:
    papers = list(papers)
    date_str = datetime.now().strftime("%Y-%m-%d")
    if not papers:
        return f"<b>{date_str} Daily Paper Report</b>\n\nNo selected papers in this run."

    lines: List[str] = [
        f"<b>{date_str} Daily Paper Report</b>",
        f"Selected papers: <b>{len(papers)}</b>",
        "",
    ]
    for index, paper in enumerate(papers, 1):
        title = html.escape(paper["title"])
        url = html.escape(paper.get("url", ""))
        lines.append(f"<b>{index}. <a href=\"{url}\">{title}</a></b>")
        lines.append(f"Score: <b>{paper.get('score', 0)}/10</b>")
        if paper.get("score_reason"):
            lines.append(f"Why selected: {html.escape(paper['score_reason'])}")
        if paper.get("code_url"):
            lines.append(f"<a href=\"{html.escape(paper['code_url'])}\">Code link</a>")
        lines.append("")
    if doc_url:
        lines.append(f"<a href=\"{html.escape(doc_url)}\">Feishu doc</a>")
    return "\n".join(lines).strip()


def build_slack_blocks(papers: Iterable[Dict], doc_url: Optional[str] = None) -> List[dict]:
    papers = list(papers)
    date_str = datetime.now().strftime("%Y-%m-%d")
    if not papers:
        return [
            {"type": "header", "text": {"type": "plain_text", "text": f"{date_str} Daily Paper Report"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "No selected papers in this run."}},
        ]

    blocks: List[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{date_str} Daily Paper Report"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Selected papers: *{len(papers)}*"}]},
    ]
    for index, paper in enumerate(papers[:8], 1):
        text_lines = [
            f"*{index}. <{paper.get('url', '')}|{paper['title']}>*",
            f"Score: *{paper.get('score', 0)}/10*",
        ]
        if paper.get("score_reason"):
            text_lines.append(f"Why selected: {paper['score_reason']}")
        if paper.get("code_url"):
            text_lines.append(f"<{paper['code_url']}|Code link>")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(text_lines)}})
        blocks.append({"type": "divider"})
    if doc_url:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"<{doc_url}|Feishu doc>"}})
    return blocks


def build_conference_plaintext(summary: dict) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines: List[str] = [f"{date_str} Conference Monitor", "", summary.get("message", "Conference status checked.")]
    venue_counts = summary.get("venue_counts", {})
    if venue_counts:
        lines.extend(["", "Detected venues:"])
        for venue, count in sorted(venue_counts.items()):
            relevant = summary.get("relevant_by_venue", {}).get(venue, 0)
            lines.append(f"- {venue}: new {count}, relevant {relevant}")
    not_released = summary.get("not_released", [])
    if not_released:
        lines.extend(["", "Not released yet:"])
        for venue in sorted(not_released):
            lines.append(f"- {venue}")
    if summary.get("doc_url"):
        lines.extend(["", "Feishu doc:", summary["doc_url"]])
    return "\n".join(lines).strip()


def build_conference_telegram_html(summary: dict) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines: List[str] = [f"<b>{date_str} Conference Monitor</b>", "", html.escape(summary.get("message", "Conference status checked."))]
    venue_counts = summary.get("venue_counts", {})
    if venue_counts:
        lines.extend(["", "<b>Detected venues</b>"])
        for venue, count in sorted(venue_counts.items()):
            relevant = summary.get("relevant_by_venue", {}).get(venue, 0)
            lines.append(f"• {html.escape(venue)}: new <b>{count}</b>, relevant <b>{relevant}</b>")
    not_released = summary.get("not_released", [])
    if not_released:
        lines.extend(["", "<b>Not released yet</b>"])
        for venue in sorted(not_released):
            lines.append(f"• {html.escape(venue)}")
    if summary.get("doc_url"):
        lines.extend(["", f'<a href="{html.escape(summary["doc_url"])}">Feishu doc</a>'])
    return "\n".join(lines).strip()


def build_conference_slack_blocks(summary: dict) -> List[dict]:
    date_str = datetime.now().strftime("%Y-%m-%d")
    blocks: List[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{date_str} Conference Monitor"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": summary.get("message", "Conference status checked.")}},
    ]
    venue_counts = summary.get("venue_counts", {})
    if venue_counts:
        venue_lines = []
        for venue, count in sorted(venue_counts.items()):
            relevant = summary.get("relevant_by_venue", {}).get(venue, 0)
            venue_lines.append(f"*{venue}*: new {count}, relevant {relevant}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(venue_lines)}})
    not_released = summary.get("not_released", [])
    if not_released:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Not released yet*\n" + "\n".join(f"• {venue}" for venue in sorted(not_released))}})
    if summary.get("doc_url"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"<{summary['doc_url']}|Feishu doc>"}})
    return blocks
