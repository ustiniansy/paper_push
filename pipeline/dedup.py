"""
去重模块：基于 SQLite 记录已处理/已推送的论文，避免重复评分和推送。
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, List


def _db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "db", "papers.db")


def _init_db():
    path = _db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_papers (
            arxiv_id       TEXT PRIMARY KEY,
            title          TEXT,
            score          REAL    DEFAULT 0,
            sent           INTEGER DEFAULT 0,   -- 1=已推送
            source         TEXT,
            processed_date TEXT,
            sent_date      TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def filter_unseen(papers: List[Dict]) -> List[Dict]:
    """过滤掉数据库中已有记录的论文，返回全新的论文列表。"""
    _init_db()
    conn = sqlite3.connect(_db_path())
    seen = {row[0] for row in conn.execute("SELECT arxiv_id FROM seen_papers")}
    conn.close()

    new = [p for p in papers if p["arxiv_id"] not in seen]
    print(
        f"[去重] {len(papers)} 篇 → {len(new)} 篇新论文"
        f"（过滤 {len(papers) - len(new)} 篇已处理过）"
    )
    return new


def mark_processed(papers: List[Dict]):
    """
    将论文标记为"已处理"（参与过评分），防止明天重复评分。
    不影响 sent 状态。
    """
    if not papers:
        return
    _init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(_db_path())
    conn.executemany(
        """
        INSERT OR IGNORE INTO seen_papers
            (arxiv_id, title, score, sent, source, processed_date)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        [
            (
                p["arxiv_id"],
                p.get("title", "")[:500],
                p.get("score", 0),
                p.get("source", ""),
                today,
            )
            for p in papers
        ],
    )
    conn.commit()
    conn.close()


def mark_sent(papers: List[Dict]):
    """将论文标记为"已推送"，更新评分和推送日期。"""
    if not papers:
        return
    _init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(_db_path())
    conn.executemany(
        """
        INSERT OR REPLACE INTO seen_papers
            (arxiv_id, title, score, sent, source, processed_date, sent_date)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        """,
        [
            (
                p["arxiv_id"],
                p.get("title", "")[:500],
                p.get("score", 0),
                p.get("source", ""),
                today,
                today,
            )
            for p in papers
        ],
    )
    conn.commit()
    conn.close()
