"""
Hugging Face Daily Papers source.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

HF_API_URL = "https://huggingface.co/api/daily_papers"
HF_MAX_LIMIT = 100


def _parse_hf_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_hf_papers(
    limit: int = 50,
    timeout: int = 30,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    raise_on_error: bool = False,
) -> List[Dict]:
    """
    Fetch papers from the Hugging Face Daily Papers API and optionally filter by UTC time window.
    The time window uses `submittedOnDailyAt` when available, otherwise `publishedAt`.
    """
    print("[HuggingFace] 正在抓取 Daily Papers API...")

    if limit > HF_MAX_LIMIT:
        print(f"[HuggingFace] limit={limit} exceeds API max; capping to {HF_MAX_LIMIT}")
        limit = HF_MAX_LIMIT

    try:
        resp = requests.get(
            HF_API_URL,
            params={"limit": limit},
            timeout=timeout,
            headers={"User-Agent": "paper-push-bot/1.0"},
        )
        resp.raise_for_status()
        items = resp.json()
    except (requests.RequestException, ValueError) as exc:
        if raise_on_error:
            raise RuntimeError(f"HuggingFace Daily Papers request failed: {exc}") from exc
        print(f"[HuggingFace] 请求失败: {exc}")
        return []

    papers: List[Dict] = []
    for item in items:
        paper_info = item.get("paper", {})
        arxiv_id = paper_info.get("id", "").strip()
        if not arxiv_id:
            continue

        submitted_at = _parse_hf_datetime(paper_info.get("submittedOnDailyAt", ""))
        published_at = _parse_hf_datetime(paper_info.get("publishedAt", ""))
        sort_time = submitted_at or published_at
        if since and sort_time and sort_time < since:
            continue
        if until and sort_time and sort_time >= until:
            continue

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": paper_info.get("title", "").strip(),
                "abstract": paper_info.get("summary", "").strip(),
                "authors": [author.get("name", "") for author in paper_info.get("authors", [])],
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "source": "huggingface",
                "categories": [],
                "upvotes": item.get("upvotes", 0) or paper_info.get("upvotes", 0),
                "published_at": published_at.isoformat() if published_at else "",
                "submitted_at": submitted_at.isoformat() if submitted_at else "",
            }
        )

    print(f"[HuggingFace] 获取到 {len(papers)} 篇论文")
    return papers
