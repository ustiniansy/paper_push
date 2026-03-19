"""
HuggingFace Daily Papers 数据源
官方 API: https://huggingface.co/api/daily_papers
"""
from typing import Dict, List

import requests

HF_API_URL = "https://huggingface.co/api/daily_papers"


def fetch_hf_papers(limit: int = 50, timeout: int = 30) -> List[Dict]:
    """
    从 HuggingFace Daily Papers API 获取当日精选论文。

    Args:
        limit:   最多获取篇数
        timeout: 请求超时秒数

    Returns:
        论文字典列表，字段同 arxiv_source，upvotes 有真实数值
    """
    print(f"[HuggingFace] 正在抓取 Daily Papers API...")

    try:
        resp = requests.get(
            HF_API_URL,
            params={"limit": limit},
            timeout=timeout,
            headers={"User-Agent": "paper-push-bot/1.0"},
        )
        resp.raise_for_status()
        items = resp.json()
    except requests.RequestException as e:
        print(f"[HuggingFace] 请求失败: {e}")
        return []
    except ValueError as e:
        print(f"[HuggingFace] JSON 解析失败: {e}")
        return []

    papers: List[Dict] = []

    for item in items:
        paper_info = item.get("paper", {})
        arxiv_id = paper_info.get("id", "").strip()
        if not arxiv_id:
            continue

        # upvotes 字段可能在顶层或 paper 内
        upvotes = item.get("upvotes", 0) or paper_info.get("upvotes", 0)

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": paper_info.get("title", "").strip(),
                "abstract": paper_info.get("summary", "").strip(),
                "authors": [
                    a.get("name", "") for a in paper_info.get("authors", [])
                ],
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "source": "huggingface",
                "categories": [],
                "upvotes": upvotes,
            }
        )

    print(f"[HuggingFace] 获取到 {len(papers)} 篇论文")
    return papers
