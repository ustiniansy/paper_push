"""
Personalized paper push system main entrypoint.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import yaml

from pipeline.dedup import filter_unseen, mark_processed, mark_sent
from pipeline.keyword_filter import keyword_filter
from pipeline.llm_scorer import score_papers
from pipeline.summarizer import summarize_paper
from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import (
    poll_user_reply,
    push_to_feishu,
    send_candidate_card,
    send_confirmation,
)
from sources.arxiv_source import fetch_arxiv_papers
from sources.hf_source import fetch_hf_papers

_PWC_BASE = "https://arxiv.paperswithcode.com/api/v0/papers/"
_RUNTIME_STATE_PATH = os.path.join(os.path.dirname(__file__), "db", "runtime_state.json")
_DEFAULT_INITIAL_LOOKBACK_HOURS = 48
_DEFAULT_OVERLAP_HOURS = 18


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
        resp = requests.get(
            f"{_PWC_BASE}{arxiv_id}",
            timeout=timeout,
            verify=False,
        )
        data = resp.json()
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
        f"[合并] 共 {total} 篇唯一论文"
        f"（arXiv独有: {total - from_hf_only - both}"
        f" | HF独有: {from_hf_only}"
        f" | 两源均收录: {both}）"
    )
    return list(merged.values())


def main():
    start_time = time.time()
    run_started_at = datetime.now(timezone.utc)
    local_start = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'=' * 55}")
    print(f"  论文推送系统启动  {local_start}")
    print(f"{'=' * 55}\n")

    config = load_config()
    net_cfg = config.get("network", {})
    timeout = net_cfg.get("request_timeout", 30)
    threshold = config["llm"]["score_threshold"]
    window_start, window_end = _compute_fetch_window(config, run_started_at)
    print(
        "[窗口] "
        f"{window_start.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"→ {window_end.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    print("【Step 1】数据采集")
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

    print("\n【Step 2】合并与去重")
    all_papers = merge_papers(arxiv_papers, hf_papers)
    new_papers = filter_unseen(all_papers)

    if not new_papers:
        print("\n本次窗口内暂无新论文（或均已处理），任务结束。")
        _mark_successful_run(window_end)
        return

    print("\n【Step 3】关键词过滤")
    candidates = keyword_filter(new_papers, config)
    if not candidates:
        print("关键词过滤后无候选论文，任务结束。")
        mark_processed(new_papers)
        _mark_successful_run(window_end)
        return

    print("\n【Step 4】DeepSeek 相关性评分")
    scored = score_papers(candidates, config)
    mark_processed(scored)

    scored_ids = {paper["arxiv_id"] for paper in scored}
    unscored = [paper for paper in new_papers if paper["arxiv_id"] not in scored_ids]
    mark_processed(unscored)

    selected = sorted(
        [paper for paper in scored if paper["score"] >= threshold],
        key=lambda paper: paper["score"],
        reverse=True,
    )
    if not selected:
        print(f"\n本次窗口内无论文达到评分阈值（≥ {threshold}），推送空日报。")
        push_to_feishu([], config)
        _mark_successful_run(window_end)
        return

    print(f"\n【Step 5】精选 {len(selected)} 篇论文达到阈值（≥ {threshold}），生成摘要...")
    for index, paper in enumerate(selected, 1):
        title_short = paper["title"][:55] + ("…" if len(paper["title"]) > 55 else "")
        print(f"  [{index}/{len(selected)}] {title_short}")
        paper["code_url"] = get_code_link(paper["url"], timeout=timeout)
        paper["summary_text"] = summarize_paper(paper, config)
        if index < len(selected):
            time.sleep(1)

    print("\n【Step 6】飞书群消息推送 / 交互选择")
    chat_id = config.get("feishu", {}).get("chat_id", "")
    if chat_id:
        msg_id = send_candidate_card(selected, config)
        if not msg_id:
            print("[飞书Bot] 候选卡片发送失败，回退为 webhook 总览卡片并默认全选。")
            push_to_feishu(selected, config)
            indices = list(range(len(selected)))
        else:
            indices = poll_user_reply(config, total=len(selected))
        chosen = [selected[index] for index in indices]
        if not chosen:
            print("用户取消选择，跳过知识库写入。")
            mark_sent(selected)
            _mark_successful_run(window_end)
            return
        send_confirmation(config, f"✅ 已收到，正在整理 {len(chosen)} 篇论文到知识库...")
    else:
        push_to_feishu(selected, config)
        for index, paper in enumerate(selected, 1):
            src = "🤗" if paper.get("source") == "huggingface" else "📄"
            upvotes = f" 👍{paper['upvotes']}" if paper.get("upvotes", 0) > 0 else ""
            print(f"  {index}. [{paper['score']}分] {src}{upvotes} {paper['title'][:65]}")
        print("\n输入要保留的序号（如 1,3,5-8 或 all），留空=全部保留：")
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        if not raw or raw.lower() == "all":
            chosen = list(selected)
        else:
            chosen_indices = set()
            for part in raw.split(","):
                part = part.strip()
                if "-" in part:
                    low, high = part.split("-", 1)
                    for number in range(int(low), int(high) + 1):
                        if 1 <= number <= len(selected):
                            chosen_indices.add(number - 1)
                else:
                    number = int(part)
                    if 1 <= number <= len(selected):
                        chosen_indices.add(number - 1)
            chosen = [selected[index] for index in sorted(chosen_indices)] if chosen_indices else list(selected)

    print(f"\n已选择 {len(chosen)} 篇，写入知识库...")
    print("\n【Step 7】飞书知识库文档")
    doc_url = create_daily_document(chosen, config)

    if doc_url:
        send_confirmation(config, f"改好了，文档已更新：{doc_url}")
    else:
        send_confirmation(config, "改好了。")

    mark_sent(selected)
    _mark_successful_run(window_end)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 55}")
    print(f"  ✅ 任务完成！精选 {len(selected)} 篇，耗时 {elapsed:.0f}s")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
