"""
arXiv source based on the combined category RSS feed.
"""
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, List, Optional

import feedparser


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fed = []

    def handle_data(self, data):
        self.fed.append(data)

    def get_data(self):
        return "".join(self.fed)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_data().strip()


def _extract_arxiv_id(identifier: str) -> str:
    """Extract the canonical arXiv id without version suffix."""
    match = re.search(r"arxiv\.org/abs/([^\s/?#]+)", identifier, re.IGNORECASE)
    if match:
        return match.group(1).split("v")[0]

    match = re.search(r"arXiv\.org:([^\s]+)", identifier, re.IGNORECASE)
    if match:
        return match.group(1).split("v")[0]

    match = re.search(r"\b(\d{4}\.\d{4,5})\b", identifier)
    return match.group(1) if match else ""


def _clean_title(title: str) -> str:
    return re.sub(r"\s*\(arXiv:[^)]+\)\s*$", "", title).strip()


def _clean_abstract(raw: str) -> str:
    text = _strip_html(raw)
    text = re.sub(
        r"^arXiv:\S+\s+Announce\s+Type:\s+\S+\s*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^Abstract\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*Subjects?\s*:.*$", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _to_utc_datetime(entry) -> Optional[datetime]:
    published = getattr(entry, "published_parsed", None)
    if not published:
        return None
    return datetime(*published[:6], tzinfo=timezone.utc)


def fetch_arxiv_papers(
    categories: List[str],
    timeout: int = 30,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    raise_on_error: bool = False,
) -> List[Dict]:
    """
    Fetch papers from the arXiv RSS feed and optionally filter by UTC time window.
    """
    cat_query = "+".join(categories)
    url = f"https://rss.arxiv.org/rss/{cat_query}"
    print(f"[arXiv] 正在抓取 RSS: {url}")

    feed = feedparser.parse(url, request_headers={"User-Agent": "paper-push-bot/1.0"})
    if feed.bozo and not feed.entries:
        if raise_on_error:
            raise RuntimeError(f"arXiv RSS parse failed: {feed.bozo_exception}")
        print(f"[arXiv] RSS 解析异常: {feed.bozo_exception}")
        return []

    papers: Dict[str, Dict] = {}
    for entry in feed.entries:
        arxiv_id = _extract_arxiv_id(entry.get("id", ""))
        if not arxiv_id:
            continue

        published_at = _to_utc_datetime(entry)
        if since and published_at and published_at < since:
            continue
        if until and published_at and published_at >= until:
            continue

        raw_authors = getattr(entry, "authors", [])
        if raw_authors:
            joined = ", ".join(a.get("name", "") for a in raw_authors)
            authors = [author.strip() for author in joined.split(",") if author.strip()]
        else:
            authors = []

        papers[arxiv_id] = {
            "arxiv_id": arxiv_id,
            "title": _clean_title(entry.get("title", "")),
            "abstract": _clean_abstract(entry.get("summary", entry.get("description", ""))),
            "authors": authors,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "source": "arxiv",
            "categories": [tag.get("term", "") for tag in getattr(entry, "tags", [])],
            "upvotes": 0,
            "published_at": published_at.isoformat() if published_at else "",
        }

    print(f"[arXiv] 获取到 {len(papers)} 篇论文")
    return list(papers.values())
