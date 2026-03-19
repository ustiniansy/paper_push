"""
Repush high-scoring papers from SQLite without rerunning collection.
"""
import argparse
import sqlite3
import time
import xml.etree.ElementTree as ET

from main import get_code_link, load_config
from pipeline.dedup import mark_processed
from pipeline.http_client import get_retry_session
from pipeline.llm_scorer import score_papers
from pipeline.publish_flow import (
    choose_papers_for_delivery,
    prepare_papers_for_delivery,
    write_selected_papers,
)
from pipeline.runtime_utils import is_dry_run, log

_ARXIV_API = "http://export.arxiv.org/api/query"


def fetch_abstracts(papers, timeout=30):
    """Populate missing abstracts from the arXiv API in batches of 50."""
    need = [paper for paper in papers if not paper.get("abstract")]
    if not need:
        return

    print(f"  从 arXiv API 补充 {len(need)} 篇摘要...")
    for start in range(0, len(need), 50):
        batch = need[start : start + 50]
        ids = ",".join(paper["arxiv_id"] for paper in batch)
        try:
            resp = get_retry_session().get(
                _ARXIV_API,
                params={"id_list": ids, "max_results": len(batch)},
                timeout=timeout,
            )
            root = ET.fromstring(resp.text)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            abstract_map = {}
            for entry in root.findall("a:entry", ns):
                aid_full = entry.find("a:id", ns).text.strip()
                aid = aid_full.split("/abs/")[-1].split("v")[0]
                abstract_map[aid] = entry.find("a:summary", ns).text.strip()
            for paper in batch:
                if paper["arxiv_id"] in abstract_map:
                    paper["abstract"] = abstract_map[paper["arxiv_id"]]
        except Exception as exc:
            print(f"  ⚠️ arXiv API 请求失败: {exc}")
        if start + 50 < len(need):
            time.sleep(3)


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without Feishu pushes, docs writes, or database updates.",
    )
    return parser.parse_args()


def backfill_score_reasons(papers, config):
    missing = [paper for paper in papers if not paper.get("score_reason")]
    if not missing:
        return

    print(f"  回填 {len(missing)} 篇论文的 score reason...")
    score_papers(missing, config)
    if not is_dry_run(config):
        mark_processed(missing)


def main():
    args = parse_args()
    start_time = time.time()
    config = load_config()
    if args.dry_run:
        config.setdefault("runtime", {})["dry_run"] = True

    threshold = config["llm"]["score_threshold"]
    timeout = config.get("network", {}).get("request_timeout", 30)
    if is_dry_run(config):
        log("DryRun", "repush 运行在 dry-run 模式，不会推送飞书或更新数据库。")

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

    papers = [
        {
            "arxiv_id": row["arxiv_id"],
            "title": row["title"],
            "score": row["score"],
            "score_reason": row["score_reason"] or "",
            "source": row["source"] or "arxiv",
            "upvotes": 0,
            "url": f"https://arxiv.org/abs/{row['arxiv_id']}",
            "abstract": "",
        }
        for row in rows
    ]

    if not papers:
        print(f"数据库中无 ≥ {threshold} 分的论文。")
        return

    fetch_abstracts(papers, timeout=timeout)
    backfill_score_reasons(papers, config)

    print(f"\n共 {len(papers)} 篇论文达到阈值（≥ {threshold}），生成摘要...\n")
    prepare_papers_for_delivery(
        papers,
        config,
        timeout=timeout,
        code_link_getter=get_code_link,
    )

    print("\n飞书群消息推送 / 交互选择...")
    chosen = choose_papers_for_delivery(
        papers,
        config,
        poll_timeout_minutes=args.poll_timeout,
    )
    if not chosen:
        elapsed = time.time() - start_time
        print(f"\n✅ 完成！耗时 {elapsed:.0f}s")
        return

    write_selected_papers(chosen, config)

    elapsed = time.time() - start_time
    print(f"\n✅ 完成！{len(chosen)} 篇入库，耗时 {elapsed:.0f}s")


if __name__ == "__main__":
    main()
