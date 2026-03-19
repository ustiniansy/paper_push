"""
SQLite-backed deduplication for processed and sent papers.
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List

_SQLITE_IN_MAX = 900


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
            score_reason   TEXT,
            sent           INTEGER DEFAULT 0,
            source         TEXT,
            processed_date TEXT,
            sent_date      TEXT
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(seen_papers)")}
    if "score_reason" not in columns:
        conn.execute("ALTER TABLE seen_papers ADD COLUMN score_reason TEXT")
    conn.commit()
    conn.close()


def _chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _fetch_seen_ids(conn: sqlite3.Connection, ids: List[str]) -> set[str]:
    if not ids:
        return set()

    seen: set[str] = set()
    for chunk in _chunked(ids, _SQLITE_IN_MAX):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT arxiv_id FROM seen_papers WHERE arxiv_id IN ({placeholders})",
            chunk,
        )
        seen.update(row[0] for row in rows)
    return seen


def filter_unseen(papers: List[Dict]) -> List[Dict]:
    """Return only papers whose ids are not already recorded in SQLite."""
    _init_db()
    conn = sqlite3.connect(_db_path())
    seen = _fetch_seen_ids(conn, [paper["arxiv_id"] for paper in papers])
    conn.close()

    new = [paper for paper in papers if paper["arxiv_id"] not in seen]
    print(
        f"[去重] {len(papers)} 篇 → {len(new)} 篇新论文"
        f"（过滤 {len(papers) - len(new)} 篇已处理过）"
    )
    return new


def mark_processed(papers: List[Dict]):
    """Mark papers as processed so they will not be rescored next run."""
    if not papers:
        return

    _init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(_db_path())
    conn.executemany(
        """
        INSERT INTO seen_papers
            (arxiv_id, title, score, score_reason, sent, source, processed_date)
        VALUES (?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(arxiv_id) DO UPDATE SET
            title = excluded.title,
            score = excluded.score,
            score_reason = excluded.score_reason,
            source = excluded.source,
            processed_date = excluded.processed_date
        """,
        [
            (
                paper["arxiv_id"],
                paper.get("title", "")[:500],
                paper.get("score", 0),
                paper.get("score_reason", ""),
                paper.get("source", ""),
                today,
            )
            for paper in papers
        ],
    )
    conn.commit()
    conn.close()


def mark_sent(papers: List[Dict]):
    """Mark papers as sent and update their score metadata."""
    if not papers:
        return

    _init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(_db_path())
    conn.executemany(
        """
        INSERT INTO seen_papers
            (arxiv_id, title, score, score_reason, sent, source, processed_date, sent_date)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(arxiv_id) DO UPDATE SET
            title = excluded.title,
            score = excluded.score,
            score_reason = excluded.score_reason,
            sent = 1,
            source = excluded.source,
            processed_date = excluded.processed_date,
            sent_date = excluded.sent_date
        """,
        [
            (
                paper["arxiv_id"],
                paper.get("title", "")[:500],
                paper.get("score", 0),
                paper.get("score_reason", ""),
                paper.get("source", ""),
                today,
                today,
            )
            for paper in papers
        ],
    )
    conn.commit()
    conn.close()
