"""
arXiv 数据源
通过 RSS Feed 获取当日新增论文（arXiv 每个工作日发布一次公告）
"""
import re
from html.parser import HTMLParser
from typing import Dict, List

import feedparser


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


def _strip_html(html: str) -> str:
    s = _HTMLStripper()
    s.feed(html)
    return s.get_data().strip()


def _extract_arxiv_id(identifier: str) -> str:
    """从 URL 或 OAI 标识符中提取 arXiv ID，去除版本号。
    支持：
      https://arxiv.org/abs/2501.12345v1  → 2501.12345
      oai:arXiv.org:2501.12345v1          → 2501.12345
    """
    # URL 格式
    match = re.search(r"arxiv\.org/abs/([^\s/?#]+)", identifier, re.IGNORECASE)
    if match:
        return match.group(1).split("v")[0]
    # OAI 格式：oai:arXiv.org:XXXX.XXXXXvN
    match = re.search(r"arXiv\.org:([^\s]+)", identifier, re.IGNORECASE)
    if match:
        return match.group(1).split("v")[0]
    # 兜底：直接匹配 XXXX.XXXXX 数字格式
    match = re.search(r"\b(\d{4}\.\d{4,5})\b", identifier)
    return match.group(1) if match else ""


def _clean_title(title: str) -> str:
    """去掉 arXiv RSS 标题末尾的 '(arXiv:xxxx.xxxxx v1)' 部分。"""
    return re.sub(r"\s*\(arXiv:[^)]+\)\s*$", "", title).strip()


def _clean_abstract(raw: str) -> str:
    """从 RSS summary 字段提取纯文本摘要。
    arXiv RSS summary 格式：
      'arXiv:XXXX.XXXXXvN Announce Type: new\\nAbstract: ...'
    """
    text = _strip_html(raw)
    # 去掉 "arXiv:XXX Announce Type: new/cross/replace" 前缀（含换行）
    text = re.sub(
        r"^arXiv:\S+\s+Announce\s+Type:\s+\S+\s*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # 去掉 "Abstract:" 前缀
    text = re.sub(r"^Abstract\s*:\s*", "", text, flags=re.IGNORECASE)
    # 去掉末尾 "Subjects: ..." 行
    text = re.sub(r"\s*Subjects?\s*:.*$", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def fetch_arxiv_papers(categories: List[str], timeout: int = 30) -> List[Dict]:
    """
    从 arXiv RSS Feed 获取今日新增论文。

    Args:
        categories: arXiv 类别列表，如 ['cs.CV', 'cs.AI', 'cs.LG']
        timeout:    请求超时秒数

    Returns:
        论文字典列表，每条包含：
        arxiv_id, title, abstract, authors, url, source, categories, upvotes
    """
    cat_query = "+".join(categories)
    url = f"https://rss.arxiv.org/rss/{cat_query}"
    print(f"[arXiv] 正在抓取 RSS: {url}")

    feed = feedparser.parse(url, request_headers={"User-Agent": "paper-push-bot/1.0"})

    if feed.bozo and not feed.entries:
        print(f"[arXiv] RSS 解析异常: {feed.bozo_exception}")
        return []

    papers: Dict[str, Dict] = {}

    for entry in feed.entries:
        arxiv_id = _extract_arxiv_id(entry.get("id", ""))
        if not arxiv_id:
            continue

        title = _clean_title(entry.get("title", ""))
        abstract = _clean_abstract(
            entry.get("summary", entry.get("description", ""))
        )
        # arXiv RSS 的 author 字段可能是单个逗号分隔字符串，也可能是列表
        raw_authors = getattr(entry, "authors", [])
        if raw_authors:
            joined = ", ".join(a.get("name", "") for a in raw_authors)
            # 按逗号拆分并去空格
            authors = [a.strip() for a in joined.split(",") if a.strip()]
        else:
            authors = []
        cats = [
            t.get("term", "") for t in getattr(entry, "tags", [])
        ]

        papers[arxiv_id] = {
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "source": "arxiv",
            "categories": cats,
            "upvotes": 0,
        }

    print(f"[arXiv] 获取到 {len(papers)} 篇论文")
    return list(papers.values())
