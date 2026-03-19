"""
关键词快速过滤：在 LLM 评分前廉价筛掉明显不相关的论文，降低 API 成本。

过滤规则（满足其一即通过）：
  A. 命中任意 1 个【高优先级】关键词（全词匹配，不误匹配子串）
  B. 命中任意 2 个【中优先级】关键词（避免单个宽泛词如 'LLM' 独自通过）
"""
import re
from typing import Dict, List


def _make_pattern(keyword: str) -> re.Pattern:
    """为关键词构造全词边界正则，支持带空格的多词短语。"""
    escaped = re.escape(keyword)
    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


def keyword_filter(papers: List[Dict], config: dict) -> List[Dict]:
    """
    Args:
        papers: 待过滤论文列表
        config: 完整配置字典

    Returns:
        通过关键词匹配的论文列表
    """
    kw_cfg = config["research_profile"]["keywords"]
    high_patterns = [_make_pattern(k) for k in kw_cfg.get("high_priority", [])]
    medium_patterns = [_make_pattern(k) for k in kw_cfg.get("medium_priority", [])]

    passed, dropped = [], []
    for paper in papers:
        text = paper.get("title", "") + " " + paper.get("abstract", "")

        # 规则 A：命中任意高优先级关键词
        if any(p.search(text) for p in high_patterns):
            passed.append(paper)
            continue

        # 规则 B：同时命中 ≥2 个中优先级关键词
        medium_hits = sum(1 for p in medium_patterns if p.search(text))
        if medium_hits >= 2:
            passed.append(paper)
        else:
            dropped.append(paper)

    print(
        f"[关键词过滤] {len(papers)} 篇 → {len(passed)} 篇候选"
        f"（过滤 {len(dropped)} 篇）"
    )
    return passed
