"""
从数据库取已评分论文，跳过采集/评分，直接走：
  摘要 → 飞书推送 → 交互选择 → 确认 → 知识库 → 通知
"""
import argparse
import sqlite3
import time
import xml.etree.ElementTree as ET

import requests

from main import (
    load_config,
    get_code_link,
)

from pipeline.llm_scorer import score_papers
from pipeline.summarizer import summarize_paper
from pipeline.dedup import mark_processed, mark_sent
from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import (
    push_to_feishu,
    send_candidate_card,
    poll_user_reply,
    send_confirmation,
)

_ARXIV_API = "http://export.arxiv.org/api/query"


def fetch_abstracts(papers, timeout=30):
    """批量从 arXiv API 补充 abstract（每次最多 50 篇）。"""
    need = [p for p in papers if not p.get("abstract")]
    if not need:
        return
    print(f"  从 arXiv API 补充 {len(need)} 篇摘要...")
    for start in range(0, len(need), 50):
        batch = need[start:start + 50]
        ids = ",".join(p["arxiv_id"] for p in batch)
        try:
            resp = requests.get(
                _ARXIV_API,
                params={"id_list": ids, "max_results": len(batch)},
                timeout=timeout,
            )
            root = ET.fromstring(resp.text)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry", ns):
                aid_full = entry.find("a:id", ns).text.strip()
                aid = aid_full.split("/abs/")[-1].split("v")[0]
                abstract = entry.find("a:summary", ns).text.strip()
                # 匹配回 papers
                for p in batch:
                    if p["arxiv_id"] == aid:
                        p["abstract"] = abstract
                        break
        except Exception as e:
            print(f"  ⚠️ arXiv API 请求失败: {e}")
        if start + 50 < len(need):
            time.sleep(3)  # arXiv API 限速


def parse_args():
    parser = argparse.ArgumentParser(description="Repush scored papers from SQLite.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only repush the top N scored papers. 0 means no limit.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=60,
        help="Feishu group reply timeout in minutes.",
    )
    return parser.parse_args()


def backfill_score_reasons(papers, config):
    missing = [p for p in papers if not p.get("score_reason")]
    if not missing:
        return

    print(f"  回填 {len(missing)} 篇论文的 score reason...")
    score_papers(missing, config)
    mark_processed(missing)


def main():
    args = parse_args()
    start_time = time.time()
    config = load_config()
    threshold = config["llm"]["score_threshold"]
    timeout = config.get("network", {}).get("request_timeout", 30)

    # ── 从数据库取 ≥ threshold 的论文 ──
    conn = sqlite3.connect("db/papers.db")
    conn.row_factory = sqlite3.Row
    query = (
        "SELECT arxiv_id, title, score, score_reason, source "
        "FROM seen_papers "
        "WHERE score >= ? "
        "ORDER BY score DESC"
    )
    params = [threshold]
    if args.limit > 0:
        query += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    papers = []
    for r in rows:
        papers.append({
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "score": r["score"],
            "score_reason": r["score_reason"] or "",
            "source": r["source"] or "arxiv",
            "upvotes": 0,
            "url": f"https://arxiv.org/abs/{r['arxiv_id']}",
            "abstract": "",
        })

    if not papers:
        print(f"数据库中无 ≥ {threshold} 分的论文。")
        return

    # ── 补充 abstract ──
    fetch_abstracts(papers, timeout=timeout)
    backfill_score_reasons(papers, config)

    # ── 摘要 + 代码链接 ──
    print(f"\n共 {len(papers)} 篇论文达到阈值（≥ {threshold}），生成摘要...\n")
    for i, paper in enumerate(papers, 1):
        title_short = paper["title"][:55] + ("…" if len(paper["title"]) > 55 else "")
        print(f"  [{i}/{len(papers)}] {title_short}")
        paper["code_url"] = get_code_link(paper["url"], timeout=timeout)
        paper["summary_text"] = summarize_paper(paper, config)
        if i < len(papers):
            time.sleep(1)

    # ── 飞书群消息推送 / 交互选择 ──
    print("\n飞书群消息推送 / 交互选择...")
    chat_id = config.get("feishu", {}).get("chat_id", "")
    if chat_id:
        msg_id = send_candidate_card(papers, config)
        if not msg_id:
            print("[飞书Bot] 候选卡片发送失败，回退为 webhook 总览卡片并默认全选。")
            push_to_feishu(papers, config)
            indices = list(range(len(papers)))
        else:
            indices = poll_user_reply(
                config,
                total=len(papers),
                timeout_minutes=args.poll_timeout,
            )
        chosen = [papers[i] for i in indices]
        if not chosen:
            print("用户取消选择，跳过知识库写入。")
            mark_sent(papers)
            elapsed = time.time() - start_time
            print(f"\n✅ 完成！耗时 {elapsed:.0f}s")
            return
        send_confirmation(config, f"✅ 已收到，正在整理 {len(chosen)} 篇论文到知识库...")
    else:
        push_to_feishu(papers, config)
        # 回退：终端交互
        for i, p in enumerate(papers, 1):
            src = "🤗" if p.get("source") == "huggingface" else "📄"
            upvotes = f" 👍{p['upvotes']}" if p.get("upvotes", 0) > 0 else ""
            print(f"  {i}. [{p['score']}分] {src}{upvotes} {p['title'][:65]}")
        print(f"\n输入要保留的序号（如 1,3,5-8 或 all），留空=全部保留：")
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        if not raw or raw.lower() == "all":
            chosen = list(papers)
        else:
            idxs = set()
            for part in raw.split(","):
                part = part.strip()
                if "-" in part:
                    lo, hi = part.split("-", 1)
                    for n in range(int(lo), int(hi) + 1):
                        if 1 <= n <= len(papers):
                            idxs.add(n - 1)
                else:
                    n = int(part)
                    if 1 <= n <= len(papers):
                        idxs.add(n - 1)
            chosen = [papers[i] for i in sorted(idxs)] if idxs else list(papers)

    print(f"\n已选择 {len(chosen)} 篇，写入知识库...")

    # ── 知识库（仅选中论文） ──
    doc_url = create_daily_document(chosen, config)

    # ── 通知完成 ──
    if doc_url:
        send_confirmation(config, f"改好了，文档已更新：{doc_url}")
    else:
        send_confirmation(config, "改好了。")

    # ── 标记已推送 ──
    mark_sent(papers)

    elapsed = time.time() - start_time
    print(f"\n✅ 完成！{len(chosen)} 篇入库，耗时 {elapsed:.0f}s")


if __name__ == "__main__":
    main()
