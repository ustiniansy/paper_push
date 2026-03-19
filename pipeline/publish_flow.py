"""
Shared paper delivery flow for main.py and repush.py.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

from pipeline.dedup import mark_sent
from pipeline.runtime_utils import is_dry_run, log
from pipeline.summarizer import summarize_paper
from publishers.registry import (
    choose_candidate_indices,
    publish_daily_digest,
    write_knowledge_base_outputs,
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
    """Use publisher capabilities to select the papers for delivery."""
    if is_dry_run(config):
        log("DryRun", f"Skip interactive selection. Keep all {len(papers)} papers.")
        return list(papers)

    indices = choose_candidate_indices(
        papers,
        config,
        poll_timeout_minutes=poll_timeout_minutes,
    )
    if indices is not None:
        return [papers[index] for index in indices]

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
    """Write selected papers to configured outputs and mark them as sent."""
    if not chosen:
        print("User skipped all papers. No knowledge-base write.")
        return None

    if is_dry_run(config):
        for result in publish_daily_digest(chosen, config, allow_network=False):
            if result.detail:
                log("Publisher", f"{result.target}: {result.status} ({result.detail})")
            else:
                log("Publisher", f"{result.target}: {result.status}")
        log("DryRun", f"Skip knowledge-base write and sent mark for {len(chosen)} papers.")
        return None

    doc_url = None
    kb_results = write_knowledge_base_outputs(chosen, config)
    for result in kb_results:
        if result.target == "feishu_docs" and result.status == "written":
            doc_url = result.detail

    for result in publish_daily_digest(chosen, config, doc_url=doc_url):
        if result.detail:
            log("Publisher", f"{result.target}: {result.status} ({result.detail})")
        else:
            log("Publisher", f"{result.target}: {result.status}")
    for result in kb_results:
        if result.detail:
            log("Publisher", f"{result.target}: {result.status} ({result.detail})")
        else:
            log("Publisher", f"{result.target}: {result.status}")
    mark_sent(chosen)
    return doc_url
