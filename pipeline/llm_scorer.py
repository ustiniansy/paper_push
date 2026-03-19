"""
LLM 相关性评分模块：使用 DeepSeek 批量评估论文与研究方向的相关性。
每批 batch_size 篇，一次 API 调用，返回 0-10 整数分。
"""
import json
import re
import time
from typing import Dict, List

from pipeline.http_client import get_default_session
from pipeline.runtime_utils import ProgressBar


def _extract_json_array(text: str) -> list:
    """从 LLM 响应中鲁棒地提取 JSON 数组（处理前后多余文本）。"""
    # 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 找到第一个 '[' 到最后一个 ']' 之间的内容
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return []


def _call_api(prompt: str, llm_config: dict) -> str:
    """调用 DeepSeek API，返回文本内容。"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_config['api_key']}",
    }
    payload = {
        "model": llm_config.get("model", "deepseek-chat"),
        "messages": [
            {
                "role": "system",
                "content": "你是严格的学术相关性评分专家，只输出合法JSON，不添加任何解释。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    resp = get_default_session().post(
        llm_config["api_url"],
        headers=headers,
        json=payload,
        timeout=llm_config.get("summary_timeout", 60),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _score_batch(batch: List[Dict], directions: List[str], llm_config: dict) -> List[Dict]:
    """对单个 batch 进行评分，失败时所有论文得 0 分。"""
    directions_str = "\n".join(f"- {d}" for d in directions)
    papers_data = [
        {
            "id": p["arxiv_id"],
            "title": p["title"],
            # 截断 abstract 节省 token，保留前 600 字符
            "abstract": p["abstract"][:600],
        }
        for p in batch
    ]

    prompt = f"""你是一个学术论文相关性评分专家。

用户研究方向：
{directions_str}

评分标准（0-10 整数）：
- 9-10：完全符合，直接研究上述方向的核心论文
- 7-8：高度相关，方法或问题有直接交叉
- 5-6：中等相关，有部分背景或方法重叠
- 3-4：弱相关，仅在概念层面有联系
- 0-2：不相关

对以下论文逐一评分，仅输出 JSON 数组，不要任何其他内容：
[{{"id":"xxx","score":8,"reason":"一句话理由"}}]

论文列表：
{json.dumps(papers_data, ensure_ascii=False, separators=(",", ":"))}"""

    try:
        content = _call_api(prompt, llm_config)
        scores_list = _extract_json_array(content)
        scores_map = {item["id"]: item for item in scores_list if "id" in item}
    except Exception as e:
        print(f"  [评分] API 调用失败: {e}，本批次论文得 0 分")
        scores_map = {}

    for p in batch:
        info = scores_map.get(p["arxiv_id"], {})
        p["score"] = int(info.get("score", 0))
        p["score_reason"] = info.get("reason", "")

    return batch


def score_papers(
    papers: List[Dict],
    config: dict,
    progress_label: str = "llm-score",
) -> List[Dict]:
    """
    批量评分入口。对所有候选论文调用 DeepSeek 评分，返回附带 score 字段的列表。

    Args:
        papers: 经过关键词过滤的候选论文
        config: 完整配置字典

    Returns:
        每篇论文增加 'score' (int) 和 'score_reason' (str) 字段
    """
    if not papers:
        return papers

    llm_config = config["llm"]
    directions = config["research_profile"]["directions"]
    batch_size = llm_config.get("batch_size", 10)
    threshold = llm_config.get("score_threshold", 6)

    print(f"[LLM评分] 共 {len(papers)} 篇，每批 {batch_size}，开始评分...")
    progress = ProgressBar(progress_label, len(papers))

    scored: List[Dict] = []
    total_batches = (len(papers) + batch_size - 1) // batch_size

    for i in range(0, len(papers), batch_size):
        batch = papers[i : i + batch_size]
        batch_no = i // batch_size + 1
        print(f"  批次 {batch_no}/{total_batches}（{len(batch)} 篇）...")

        scored_batch = _score_batch(batch, directions, llm_config)
        scored.extend(scored_batch)
        progress.advance(len(scored_batch), detail=f"batch {batch_no}/{total_batches}")

        # 批次间稍作停顿，避免触发限速
        if batch_no < total_batches:
            time.sleep(0.5)

    above = sum(1 for p in scored if p["score"] >= threshold)
    progress.finish(detail=f"above-threshold={above}")
    print(f"[LLM评分] 完成。{above}/{len(scored)} 篇评分 ≥ {threshold}，将进入摘要阶段")
    return scored
