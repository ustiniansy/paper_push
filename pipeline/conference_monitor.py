"""
Conference publication monitor.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from pipeline.dedup import filter_unseen, mark_processed, mark_sent
from pipeline.keyword_filter import keyword_filter
from pipeline.llm_scorer import score_papers
from pipeline.runtime_utils import ProgressBar, is_dry_run, log
from pipeline.summarizer import summarize_paper
from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import push_conference_status
from sources.conference_sources import enrich_conference_papers, fetch_conference_papers

_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "db",
    "conference_state.json",
)


def _load_state() -> dict:
    if not os.path.exists(_STATE_PATH):
        return {}
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def _split_by_venue(papers: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {}
    for paper in papers:
        venue = paper.get("venue", "Unknown")
        grouped.setdefault(venue, []).append(paper)
    return grouped


def _make_pattern(keyword: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)


def _relaxed_title_candidates(papers: List[Dict], config: dict) -> List[Dict]:
    kw_cfg = config["research_profile"]["keywords"]
    high_patterns = [_make_pattern(k) for k in kw_cfg.get("high_priority", [])]
    medium_patterns = [_make_pattern(k) for k in kw_cfg.get("medium_priority", [])]
    candidates: List[Dict] = []
    for paper in papers:
        title = paper.get("title", "")
        high_hit = any(pattern.search(title) for pattern in high_patterns)
        medium_hits = sum(1 for pattern in medium_patterns if pattern.search(title))
        if high_hit or medium_hits >= 1:
            paper["conference_incomplete_abstract"] = True
            candidates.append(paper)
    return candidates


def _monitor_settings(config: dict) -> tuple[int, int, Optional[list[str]], bool]:
    monitor_cfg = config.get("conference_monitor", {})
    timeout = min(
        config.get("network", {}).get("request_timeout", 30),
        monitor_cfg.get("timeout_per_source", 8),
    )
    max_workers = int(monitor_cfg.get("max_workers", 6))
    selected_venues = monitor_cfg.get("venues")
    dry_run = is_dry_run(config)
    return timeout, max_workers, selected_venues, dry_run


def _fetch_snapshot(
    config: dict,
) -> tuple[list[Dict], dict[str, int], list[str], list[str], dict[str, list[Dict]]]:
    timeout, max_workers, selected_venues, _ = _monitor_settings(config)
    all_papers, venue_counts, errors, not_released = fetch_conference_papers(
        timeout=timeout,
        selected_venues=selected_venues,
        max_workers=max_workers,
    )
    log(
        "Conference",
        f"source fetch complete: papers={len(all_papers)} venues={len(venue_counts)} "
        f"not_released={len(not_released)} errors={len(errors)}",
    )
    return all_papers, venue_counts, errors, not_released, _split_by_venue(all_papers)


def _persist_initialized_venues(papers_by_venue: Dict[str, List[Dict]]):
    _save_state(
        {
            "initialized": True,
            "initialized_venues": sorted(papers_by_venue),
        }
    )


def seed_conference_baseline(config: dict) -> dict:
    """Write the currently visible conference papers into the local DB as baseline."""
    if not config.get("conference_monitor", {}).get("enabled", True):
        return {"enabled": False}

    all_papers, venue_counts, errors, not_released, papers_by_venue = _fetch_snapshot(config)
    if all_papers:
        mark_processed(all_papers)
    _persist_initialized_venues(papers_by_venue)
    return {
        "enabled": True,
        "seeded_total": len(all_papers),
        "venue_counts": venue_counts,
        "initialized_venues": sorted(papers_by_venue),
        "errors": errors,
        "not_released": not_released,
    }


def run_conference_monitor(config: dict) -> dict:
    """Run the conference monitor and optionally push one daily status message."""
    if not config.get("conference_monitor", {}).get("enabled", True):
        return {"enabled": False}

    timeout, _, _, dry_run = _monitor_settings(config)
    threshold = config["llm"]["score_threshold"]
    state = _load_state()
    initialized_venues = set(state.get("initialized_venues", []))
    all_papers, venue_counts, errors, not_released, papers_by_venue = _fetch_snapshot(config)

    if not state.get("initialized"):
        if all_papers and not dry_run:
            mark_processed(all_papers)
            _persist_initialized_venues(papers_by_venue)
        summary = {
            "detected_total": 0,
            "relevant_total": 0,
            "venue_counts": venue_counts,
            "relevant_by_venue": {},
            "doc_url": None,
            "errors": errors,
            "not_released": not_released,
            "message": (
                f"会议论文监控已初始化，已记录当前可见的 {len(all_papers)} 篇会议论文。"
                "后续运行只提示新出现的论文。"
            ),
        }
        if dry_run:
            log("DryRun", "Skip conference initialization status push.")
        else:
            push_conference_status(summary, config)
        return summary

    seeded_venues: List[str] = []
    for venue, papers in papers_by_venue.items():
        if venue in initialized_venues:
            continue
        if not dry_run:
            mark_processed(papers)
        initialized_venues.add(venue)
        seeded_venues.append(venue)

    candidate_papers = [
        paper for paper in all_papers if paper.get("venue", "Unknown") in initialized_venues
    ]
    new_papers = filter_unseen(candidate_papers)
    log("Conference", f"candidate_papers={len(candidate_papers)} new_papers={len(new_papers)}")

    if not new_papers:
        if seeded_venues:
            message = (
                "会议基线已补全："
                f"{', '.join(sorted(seeded_venues))}。今日暂无新出现的会议论文。"
            )
        else:
            message = "今日暂无新出现的会议论文。"
        if not dry_run:
            _save_state(
                {
                    "initialized": True,
                    "initialized_venues": sorted(initialized_venues),
                }
            )
        summary = {
            "detected_total": 0,
            "relevant_total": 0,
            "venue_counts": {},
            "relevant_by_venue": {},
            "doc_url": None,
            "errors": errors,
            "not_released": not_released,
            "message": message,
        }
        if dry_run:
            log("DryRun", "Skip conference status push.")
        else:
            push_conference_status(summary, config)
        return summary

    enrich_conference_papers(new_papers, timeout=timeout)
    log("Conference", "Conference abstract enrichment complete.")
    complete_papers = [paper for paper in new_papers if paper.get("abstract", "").strip()]
    missing_abstract = [paper for paper in new_papers if not paper.get("abstract", "").strip()]
    log(
        "Conference",
        f"abstract_complete={len(complete_papers)} abstract_missing={len(missing_abstract)}",
    )

    candidates = keyword_filter(complete_papers, config)
    title_only_candidates = _relaxed_title_candidates(missing_abstract, config)
    if title_only_candidates:
        print(
            f"[Conference] {len(title_only_candidates)} papers still lack abstracts. "
            "Keeping them for title-based scoring."
        )
    candidate_ids = {paper["arxiv_id"] for paper in candidates}
    for paper in title_only_candidates:
        if paper["arxiv_id"] not in candidate_ids:
            candidates.append(paper)
            candidate_ids.add(paper["arxiv_id"])

    log("Conference", f"papers entering scoring={len(candidates)}")
    scored = score_papers(candidates, config, progress_label="conference-llm-score") if candidates else []

    if not dry_run:
        mark_processed(scored)
    scored_ids = {paper["arxiv_id"] for paper in scored}
    unscored = [paper for paper in new_papers if paper["arxiv_id"] not in scored_ids]
    if not dry_run:
        mark_processed(unscored)

    selected = sorted(
        [paper for paper in scored if paper["score"] >= threshold],
        key=lambda paper: paper["score"],
        reverse=True,
    )
    log("Conference", f"above_threshold={len(selected)}")

    doc_url: Optional[str] = None
    if selected:
        summary_progress = ProgressBar("conference-summary-generate", len(selected))
        for paper in selected:
            paper["summary_text"] = summarize_paper(paper, config)
            summary_progress.advance(detail=paper.get("venue", "Unknown"))
        summary_progress.finish()
        if dry_run:
            log("DryRun", f"Skip document write for {len(selected)} conference papers.")
        else:
            doc_url = create_daily_document(
                selected,
                config,
                title_suffix="会议论文日报",
                source_label="Conference Proceedings",
            )
            mark_sent(selected)

    relevant_by_venue: Dict[str, int] = {}
    for paper in selected:
        venue = paper.get("venue", "Unknown")
        relevant_by_venue[venue] = relevant_by_venue.get(venue, 0) + 1

    venue_detected_new: Dict[str, int] = {}
    for paper in new_papers:
        venue = paper.get("venue", "Unknown")
        venue_detected_new[venue] = venue_detected_new.get(venue, 0) + 1

    if selected:
        message = (
            f"今日检测到会议论文新增，按当前研究方向筛到 {len(selected)} 篇相关论文。"
        )
    else:
        message = (
            "今日检测到会议论文新增，但按当前研究方向未筛到高相关论文。"
        )

    if not dry_run:
        _save_state(
            {
                "initialized": True,
                "initialized_venues": sorted(initialized_venues),
            }
        )
    summary = {
        "detected_total": len(new_papers),
        "relevant_total": len(selected),
        "venue_counts": venue_detected_new,
        "relevant_by_venue": relevant_by_venue,
        "doc_url": doc_url,
        "errors": errors,
        "not_released": not_released,
        "message": message,
    }
    if dry_run:
        log("DryRun", "Skip conference status push.")
    else:
        push_conference_status(summary, config)
    return summary
