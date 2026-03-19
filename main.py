"""
个性化论文推送系统 · 每日主入口

执行流程：
  1. 读取 config.yaml（支持环境变量覆盖，适配 GitHub Actions）
  2. 从 arXiv RSS + HuggingFace Daily Papers 获取今日论文
  3. 按 arxiv_id 合并去重，过滤数据库中已处理的论文
  4. 关键词快速过滤（降低 LLM API 成本）
  5. DeepSeek 批量相关性评分（0-10）
  6. 过滤低分论文（< score_threshold），无篇数上限
  7. 逐篇生成五段式中文摘要 + 获取 PapersWithCode 代码链接
  8. 在飞书知识库创建当日文档（若已配置 App 凭证）
  9. 推送飞书群消息（总览卡片 + 逐篇详情卡片）
 10. 将所有已评分论文标记入 SQLite，防止次日重复处理
"""
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
import yaml

from pipeline.dedup import filter_unseen, mark_processed, mark_sent
from pipeline.keyword_filter import keyword_filter
from pipeline.llm_scorer import score_papers
from pipeline.summarizer import summarize_paper
from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import push_to_feishu
from sources.arxiv_source import fetch_arxiv_papers
from sources.hf_source import fetch_hf_papers


# ── 配置加载 ─────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    """
    加载配置文件，并用同名环境变量覆盖敏感字段。
    环境变量命名规则：大写下划线，如 DEEPSEEK_API_KEY、FEISHU_WEBHOOK_URL。
    """
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # GitHub Actions Secrets 覆盖
    _env_overrides = {
        "DEEPSEEK_API_KEY":        ("llm", "api_key"),
        "FEISHU_WEBHOOK_URL":       ("feishu", "webhook_url"),
        "FEISHU_APP_ID":            ("feishu", "app_id"),
        "FEISHU_APP_SECRET":        ("feishu", "app_secret"),
        "FEISHU_WIKI_SPACE_ID":     ("feishu", "wiki_space_id"),
        "FEISHU_WIKI_PARENT_NODE":  ("feishu", "wiki_parent_node"),
    }
    for env_key, (section, field) in _env_overrides.items():
        val = os.environ.get(env_key)
        if val:
            config.setdefault(section, {})[field] = val

    return config


# ── PapersWithCode 代码链接 ───────────────────────────────────

_PWC_BASE = "https://arxiv.paperswithcode.com/api/v0/papers/"


def get_code_link(paper_url: str, timeout: int = 10) -> Optional[str]:
    """查询 PapersWithCode 是否有官方代码仓库。SSL 失败时静默跳过。"""
    arxiv_id = paper_url.rstrip("/").split("/")[-1].split("v")[0]
    try:
        resp = requests.get(
            f"{_PWC_BASE}{arxiv_id}",
            timeout=timeout,
            verify=False,  # PapersWithCode SSL 握手失败时跳过验证
        )
        data = resp.json()
        official = data.get("official")
        if official and official.get("url"):
            return official["url"]
    except Exception:
        pass
    return None


# ── 数据合并 ─────────────────────────────────────────────────

def merge_papers(arxiv_papers: List[Dict], hf_papers: List[Dict]) -> List[Dict]:
    """
    合并两个来源的论文，以 arxiv_id 为主键去重。
    - HuggingFace 论文被两个来源同时收录时，保留 upvotes 并标注来源为 'both'
    - HuggingFace 独有论文直接加入
    """
    merged: Dict[str, Dict] = {p["arxiv_id"]: p for p in arxiv_papers}

    for hp in hf_papers:
        aid = hp["arxiv_id"]
        if aid in merged:
            # 已有 arXiv 版本，补充 HF 信息
            merged[aid]["upvotes"] = hp["upvotes"]
            merged[aid]["source"] = "both"
            # HF 的 abstract 通常更完整，优先使用
            if len(hp["abstract"]) > len(merged[aid]["abstract"]):
                merged[aid]["abstract"] = hp["abstract"]
        else:
            merged[aid] = hp

    total = len(merged)
    from_hf_only = sum(1 for p in merged.values() if p["source"] == "huggingface")
    both = sum(1 for p in merged.values() if p["source"] == "both")
    print(
        f"[合并] 共 {total} 篇唯一论文"
        f"（arXiv独有: {total - from_hf_only - both}"
        f" | HF独有: {from_hf_only}"
        f" | 两源均收录: {both}）"
    )
    return list(merged.values())


# ── 主流程 ───────────────────────────────────────────────────

def main():
    start_time = time.time()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*55}")
    print(f"  论文推送系统启动  {date_str}")
    print(f"{'='*55}\n")

    # ── 1. 加载配置 ──────────────────────────────────────────
    config = load_config()
    net_cfg = config.get("network", {})
    timeout = net_cfg.get("request_timeout", 30)
    threshold = config["llm"]["score_threshold"]

    # ── 2. 数据采集 ──────────────────────────────────────────
    print("【Step 1】数据采集")
    arxiv_papers = fetch_arxiv_papers(
        config["arxiv"]["categories"], timeout=timeout
    )
    hf_papers: List[Dict] = []
    if config["huggingface"]["enabled"]:
        hf_papers = fetch_hf_papers(
            limit=config["huggingface"]["limit"], timeout=timeout
        )

    # ── 3. 合并 & 数据库去重 ─────────────────────────────────
    print("\n【Step 2】合并与去重")
    all_papers = merge_papers(arxiv_papers, hf_papers)
    new_papers = filter_unseen(all_papers)

    if not new_papers:
        print("\n今日暂无新论文（均已在历史记录中），任务结束。")
        return

    # ── 4. 关键词过滤 ────────────────────────────────────────
    print("\n【Step 3】关键词过滤")
    candidates = keyword_filter(new_papers, config)

    if not candidates:
        print("关键词过滤后无候选论文，任务结束。")
        mark_processed(new_papers)
        return

    # ── 5. LLM 批量评分 ──────────────────────────────────────
    print("\n【Step 4】DeepSeek 相关性评分")
    scored = score_papers(candidates, config)

    # 将所有评分过的论文标记为已处理（防明日重复）
    mark_processed(scored)
    # 关键词过滤掉的论文也标为已处理
    scored_ids = {p["arxiv_id"] for p in scored}
    unscored = [p for p in new_papers if p["arxiv_id"] not in scored_ids]
    mark_processed(unscored)

    # ── 6. 过滤低分，无篇数上限 ──────────────────────────────
    selected = sorted(
        [p for p in scored if p["score"] >= threshold],
        key=lambda x: x["score"],
        reverse=True,
    )

    if not selected:
        print(f"\n今日无论文达到评分阈值（≥ {threshold}），推送空日报。")
        push_to_feishu([], config)
        return

    print(f"\n【Step 5】精选 {len(selected)} 篇论文，开始生成摘要")

    # ── 7. 逐篇生成摘要 & 获取代码链接 ──────────────────────
    for i, paper in enumerate(selected, 1):
        title_short = paper["title"][:55] + ("…" if len(paper["title"]) > 55 else "")
        print(f"  [{i}/{len(selected)}] {title_short}")

        paper["code_url"] = get_code_link(paper["url"], timeout=timeout)
        paper["summary_text"] = summarize_paper(paper, config)

        # 摘要间稍作停顿
        if i < len(selected):
            time.sleep(1)

    # ── 8. 飞书知识库文档（Phase 2，按需启用）────────────────
    print("\n【Step 6】飞书知识库文档")
    doc_url = create_daily_document(selected, config)

    # ── 9. 飞书群消息推送 ─────────────────────────────────────
    print("\n【Step 7】飞书群消息推送")
    push_to_feishu(selected, config, doc_url=doc_url)

    # ── 10. 标记已推送 ───────────────────────────────────────
    mark_sent(selected)

    elapsed = time.time() - start_time
    print(f"\n{'='*55}")
    print(f"  ✅ 任务完成！精选 {len(selected)} 篇，耗时 {elapsed:.0f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
