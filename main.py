"""
Personalized paper push system main entrypoint.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml

from pipeline.conference_monitor import run_conference_monitor, seed_conference_baseline
from pipeline.demo_artifacts import generate_demo_artifacts
from pipeline.config_validation import ConfigValidationError, validate_config
from pipeline.dedup import filter_unseen, mark_processed
from pipeline.http_client import get_retry_session
from pipeline.keyword_filter import keyword_filter
from pipeline.profiles import apply_profile, available_profiles
from pipeline.llm_scorer import score_papers
from pipeline.publish_flow import (
    choose_papers_for_delivery,
    prepare_papers_for_delivery,
    write_selected_papers,
)
from pipeline.runtime_utils import is_dry_run, log
from publishers.registry import publish_daily_digest
from sources.arxiv_source import fetch_arxiv_papers
from sources.hf_source import fetch_hf_papers

_PWC_BASE = "https://arxiv.paperswithcode.com/api/v0/papers/"
_RUNTIME_STATE_PATH = os.path.join(os.path.dirname(__file__), "db", "runtime_state.json")
_DEFAULT_INITIAL_LOOKBACK_HOURS = 48
_DEFAULT_OVERLAP_HOURS = 18


def parse_args():
    parser = argparse.ArgumentParser(description="Run the paper push pipeline.")
    parser.add_argument(
        "--seed-conference-baseline",
        action="store_true",
        help="Only fetch current conference papers and write them into the local DB baseline.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the pipeline without external pushes, docs writes, or state updates.",
    )
    parser.add_argument(
        "--output",
        action="append",
        choices=["feishu", "markdown", "html", "telegram", "slack"],
        help="Enable one or more output targets. Can be repeated.",
    )
    parser.add_argument(
        "--profile",
        choices=available_profiles(),
        help="Use a built-in research profile preset.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "daily",
        help="Run the daily pipeline and then the conference monitor.",
    )
    subparsers.add_parser(
        "conference",
        help="Run only the conference monitor.",
    )
    subparsers.add_parser(
        "demo",
        help="Generate local demo artifacts for screenshots and GIFs.",
    )
    return parser.parse_args()


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    env_overrides = {
        "DEEPSEEK_API_KEY": ("llm", "api_key"),
        "FEISHU_WEBHOOK_URL": ("feishu", "webhook_url"),
        "FEISHU_APP_ID": ("feishu", "app_id"),
        "FEISHU_APP_SECRET": ("feishu", "app_secret"),
        "FEISHU_WIKI_SPACE_ID": ("feishu", "wiki_space_id"),
        "FEISHU_WIKI_PARENT_NODE": ("feishu", "wiki_parent_node"),
        "FEISHU_CHAT_ID": ("feishu", "chat_id"),
    }
    for env_key, (section, field) in env_overrides.items():
        value = os.environ.get(env_key)
        if value:
            config.setdefault(section, {})[field] = value

    return config


def _load_runtime_state() -> dict:
    if not os.path.exists(_RUNTIME_STATE_PATH):
        return {}
    try:
        with open(_RUNTIME_STATE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _save_runtime_state(state: dict):
    os.makedirs(os.path.dirname(_RUNTIME_STATE_PATH), exist_ok=True)
    with open(_RUNTIME_STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _compute_fetch_window(config: dict, window_end: datetime) -> tuple[datetime, datetime]:
    fetch_cfg = config.get("fetch", {})
    initial_lookback_hours = int(
        fetch_cfg.get("initial_lookback_hours", _DEFAULT_INITIAL_LOOKBACK_HOURS)
    )
    overlap_hours = int(fetch_cfg.get("overlap_hours", _DEFAULT_OVERLAP_HOURS))

    state = _load_runtime_state()
    last_success = _parse_iso_datetime(state.get("last_success_at", ""))
    if last_success:
        window_start = last_success - timedelta(hours=overlap_hours)
    else:
        window_start = window_end - timedelta(hours=initial_lookback_hours)

    return window_start, window_end


def _mark_successful_run(window_end: datetime):
    _save_runtime_state({"last_success_at": window_end.astimezone(timezone.utc).isoformat()})


def get_code_link(paper_url: str, timeout: int = 10) -> Optional[str]:
    arxiv_id = paper_url.rstrip("/").split("/")[-1].split("v")[0]
    try:
        response = get_retry_session().get(
            f"{_PWC_BASE}{arxiv_id}",
            timeout=timeout,
            verify=False,
        )
        data = response.json()
        official = data.get("official")
        if official and official.get("url"):
            return official["url"]
    except Exception:
        pass
    return None


def merge_papers(arxiv_papers: List[Dict], hf_papers: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {paper["arxiv_id"]: paper for paper in arxiv_papers}

    for paper in hf_papers:
        arxiv_id = paper["arxiv_id"]
        if arxiv_id in merged:
            merged[arxiv_id]["upvotes"] = paper["upvotes"]
            merged[arxiv_id]["source"] = "both"
            if len(paper["abstract"]) > len(merged[arxiv_id]["abstract"]):
                merged[arxiv_id]["abstract"] = paper["abstract"]
            if paper.get("submitted_at"):
                merged[arxiv_id]["submitted_at"] = paper["submitted_at"]
        else:
            merged[arxiv_id] = paper

    total = len(merged)
    from_hf_only = sum(1 for paper in merged.values() if paper["source"] == "huggingface")
    both = sum(1 for paper in merged.values() if paper["source"] == "both")
    print(
        f"[Merge] total={total} "
        f"arxiv_only={total - from_hf_only - both} "
        f"hf_only={from_hf_only} both={both}"
    )
    return list(merged.values())


def _run_daily_pipeline(config: dict, run_started_at: datetime):
    timeout = config.get("network", {}).get("request_timeout", 30)
    threshold = config["llm"]["score_threshold"]
    dry_run = is_dry_run(config)
    window_start, window_end = _compute_fetch_window(config, run_started_at)

    print(
        "[Window] "
        f"{window_start.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} -> "
        f"{window_end.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    if dry_run:
        log("DryRun", "Enabled: no Feishu push, no document writes, no local state updates.")

    print("[Step 1] Collect papers")
    arxiv_papers = fetch_arxiv_papers(
        config["arxiv"]["categories"],
        timeout=timeout,
        since=window_start,
        until=window_end,
        raise_on_error=True,
    )
    hf_papers: List[Dict] = []
    if config["huggingface"]["enabled"]:
        hf_papers = fetch_hf_papers(
            limit=config["huggingface"]["limit"],
            timeout=timeout,
            since=window_start,
            until=window_end,
            raise_on_error=True,
        )

    print("\n[Step 2] Merge and dedup")
    all_papers = merge_papers(arxiv_papers, hf_papers)
    new_papers = filter_unseen(all_papers)

    if not new_papers:
        print("\nNo new papers in the current window.")
        for result in publish_daily_digest([], config, allow_network=not dry_run):
            if result.detail:
                log("Publisher", f"{result.target}: {result.status} ({result.detail})")
            else:
                log("Publisher", f"{result.target}: {result.status}")
        if dry_run:
            log("DryRun", "Skip empty daily push.")
    else:
        print("\n[Step 3] Keyword filter")
        candidates = keyword_filter(new_papers, config)
        log("Daily", f"new={len(new_papers)} keyword_candidates={len(candidates)}")
        if not candidates:
            print("No papers passed the keyword filter.")
            for result in publish_daily_digest([], config, allow_network=not dry_run):
                if result.detail:
                    log("Publisher", f"{result.target}: {result.status} ({result.detail})")
                else:
                    log("Publisher", f"{result.target}: {result.status}")
            if not dry_run:
                mark_processed(new_papers)
        else:
            print("\n[Step 4] LLM scoring")
            scored = score_papers(candidates, config, progress_label="daily-llm-score")
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
            log("Daily", f"above_threshold={len(selected)}")
            if not selected:
                print(f"\nNo papers reached the score threshold (>= {threshold}).")
                for result in publish_daily_digest([], config, allow_network=not dry_run):
                    if result.detail:
                        log("Publisher", f"{result.target}: {result.status} ({result.detail})")
                    else:
                        log("Publisher", f"{result.target}: {result.status}")
                if dry_run:
                    log("DryRun", "Skip empty daily push.")
            else:
                print(
                    f"\n[Step 5] Prepare delivery payload for {len(selected)} selected papers"
                )
                prepare_papers_for_delivery(
                    selected,
                    config,
                    timeout=timeout,
                    code_link_getter=get_code_link,
                )

                print("\n[Step 6] Feishu selection")
                chosen = choose_papers_for_delivery(selected, config)
                write_selected_papers(chosen, config)

    if not dry_run:
        _mark_successful_run(window_end)
    else:
        log("DryRun", "Skip runtime_state.json update.")


def _run_conference_only(config: dict):
    log("Conference", "Conference-only mode enabled: skipping daily pipeline.")
    print("\n[Conference] Monitor")
    return run_conference_monitor(config)


def _run_demo_mode(config: dict):
    log("Demo", "Generating screenshot-ready local demo artifacts.")
    print("\n[Demo] Generate local artifacts")
    return generate_demo_artifacts(config)


def main():
    args = parse_args()
    start_time = time.time()
    run_started_at = datetime.now(timezone.utc)
    local_start = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n{'=' * 55}")
    print(f"  Paper push runner started at {local_start}")
    print(f"{'=' * 55}\n")

    command = args.command or "daily"
    if command == "demo":
        config = {
            "runtime": {"outputs": ["markdown", "html"]},
            "local_output": {"output_dir": os.path.join(os.path.dirname(__file__), "output")},
            "research_profile": {"directions": ["demo showcase"]},
        }
        if getattr(args, "output", None):
            config.setdefault("runtime", {})["outputs"] = args.output
        summary = _run_demo_mode(config)
        elapsed = time.time() - start_time
        print(f"[Demo] Wrote daily={summary['daily_paths']} conference={summary['conference_paths']}")
        print(f"\n{'=' * 55}")
        print(f"  Task finished in {elapsed:.0f}s")
        print(f"{'=' * 55}\n")
        return

    config = load_config()
    if args.dry_run:
        config.setdefault("runtime", {})["dry_run"] = True
    if getattr(args, "output", None):
        config.setdefault("runtime", {})["outputs"] = args.output
    if getattr(args, "profile", None):
        config = apply_profile(config, args.profile)
        log("Config", f"Using built-in profile preset `{args.profile}`.")
    try:
        warnings = validate_config(config)
    except ConfigValidationError as exc:
        print(f"[ConfigError] {exc}")
        raise SystemExit(2)
    for warning in warnings:
        log("Config", warning)

    if args.seed_conference_baseline:
        print("[Conference] Seeding conference baseline...")
        summary = seed_conference_baseline(config)
        if not summary.get("enabled", True):
            print("[Conference] Conference monitor is disabled.")
            return
        print(
            "[Conference] Baseline seeded: "
            f"seeded={summary.get('seeded_total', 0)} "
            f"venues={len(summary.get('venue_counts', {}))} "
            f"errors={len(summary.get('errors', []))}"
        )
        if summary.get("errors"):
            print(f"[Conference] Errors: {summary['errors']}")
        elapsed = time.time() - start_time
        print(f"\n{'=' * 55}")
        print(f"  Finished in {elapsed:.0f}s")
        print(f"{'=' * 55}\n")
        return

    if command == "conference":
        summary = _run_conference_only(config)
    else:
        _run_daily_pipeline(config, run_started_at)
        print("\n[Conference] Monitor")
        summary = run_conference_monitor(config)

    if summary and summary.get("enabled", True):
        log(
            "Conference",
            f"detected={summary.get('detected_total', 0)} "
            f"relevant={summary.get('relevant_total', 0)} "
            f"errors={len(summary.get('errors', []))}",
        )

    elapsed = time.time() - start_time
    print(f"\n{'=' * 55}")
    print(f"  Task finished in {elapsed:.0f}s")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
