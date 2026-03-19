"""
Shared paper delivery flow for main.py and repush.py.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

from pipeline.dedup import mark_sent
from pipeline.runtime_utils import is_dry_run, log
from pipeline.summarizer import summarize_paper
from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import (
    poll_user_reply,
    push_to_feishu,
    send_candidate_card,
    send_confirmation,
)


def _parse_terminal_selection(raw: str, total: int) -> List[int]:
    if not raw or raw.lower() == "all":
        return list(range(total))

    chosen_indices = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            for number in range(int(low), int(high) + 1):
                if 1 <= number <= total:
                    chosen_indices.add(number - 1)
        else:
            number = int(part)
            if 1 <= number <= total:
                chosen_indices.add(number - 1)
    return sorted(chosen_indices) if chosen_indices else list(range(total))


def prepare_papers_for_delivery(
    papers: List[Dict],
    config: dict,
    timeout: int,
    code_link_getter: Callable[[str, int], Optional[str]],
):
    """Populate code links and summaries in-place."""
    log("Daily", f"Prepare code links and summaries for {len(papers)} papers.")
    for index, paper in enumerate(papers, 1):
        title_short = paper["title"][:55] + ("..." if len(paper["title"]) > 55 else "")
        print(f"  [{index}/{len(papers)}] {title_short}")
        paper["code_url"] = code_link_getter(paper["url"], timeout=timeout)
        paper["summary_text"] = summarize_paper(paper, config)
        if index < len(papers):
            time.sleep(1)
    log("Daily", "Code links and summaries ready.")


def choose_papers_for_delivery(
    papers: List[Dict],
    config: dict,
    poll_timeout_minutes: int = 60,
) -> List[Dict]:
    """Send the candidate list and return the selected papers."""
    if is_dry_run(config):
        log("DryRun", f"Skip Feishu selection. Keep all {len(papers)} papers.")
        return list(papers)

    chat_id = config.get("feishu", {}).get("chat_id", "")
    if chat_id:
        msg_id = send_candidate_card(papers, config)
        if not msg_id:
            print("[FeishuBot] Candidate card failed. Fallback to webhook digest and keep all.")
            push_to_feishu(papers, config)
            indices = list(range(len(papers)))
        else:
            indices = poll_user_reply(
                config,
                total=len(papers),
                timeout_minutes=poll_timeout_minutes,
            )
        chosen = [papers[index] for index in indices]
        if chosen:
            send_confirmation(
                config,
                f"Received. Preparing {len(chosen)} papers for the knowledge base.",
            )
        return chosen

    push_to_feishu(papers, config)
    for index, paper in enumerate(papers, 1):
        src = "HF" if paper.get("source") == "huggingface" else "arXiv"
        upvotes = f" upvotes={paper['upvotes']}" if paper.get("upvotes", 0) > 0 else ""
        print(f"  {index}. [{paper['score']}] {src}{upvotes} {paper['title'][:65]}")

    print("\nEnter the papers to keep, e.g. 1,3,5-8 or all. Empty input keeps all.")
    try:
        raw = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    indices = _parse_terminal_selection(raw, len(papers))
    return [papers[index] for index in indices]


def write_selected_papers(chosen: List[Dict], config: dict) -> Optional[str]:
    """Write selected papers to Feishu docs and mark them as sent."""
    if not chosen:
        print("User skipped all papers. No knowledge-base write.")
        return None

    if is_dry_run(config):
        log("DryRun", f"Skip knowledge-base write and sent mark for {len(chosen)} papers.")
        return None

    print(f"\nSelected {len(chosen)} papers. Writing to the knowledge base...")
    print("\n[Step 7] Feishu docs")
    doc_url = create_daily_document(chosen, config)
    if doc_url:
        send_confirmation(config, f"Done. Document updated: {doc_url}")
    else:
        send_confirmation(config, "Done.")
    mark_sent(chosen)
    return doc_url
