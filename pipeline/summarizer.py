"""
论文深度摘要模块：使用 DeepSeek 对评分达标论文逐篇生成结构化中文解读。
"""
from typing import Dict

import requests


def _call_api(prompt: str, llm_config: dict) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_config['api_key']}",
    }
    payload = {
        "model": llm_config.get("model", "deepseek-chat"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个学术分析专家，擅长将复杂的AI/CV/NLP领域论文"
                    "总结得清晰易懂，面向有一定背景知识的研究生读者。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    resp = requests.post(
        llm_config["api_url"],
        headers=headers,
        json=payload,
        timeout=llm_config.get("summary_timeout", 120),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def summarize_paper(paper: Dict, config: dict) -> str:
    """
    为单篇论文生成五段式中文深度摘要。

    Args:
        paper:  包含 title, abstract 字段的论文字典
        config: 完整配置字典

    Returns:
        结构化摘要文本（str），包含五个【】标注的部分
    """
    llm_config = config["llm"]

    prompt = f"""请根据以下论文的标题和摘要，提供中文深度分析。

论文标题：{paper['title']}
论文摘要：{paper['abstract']}

请严格按以下格式输出，不要遗漏任何部分：

【快速抓要点】
（用2-3句话说明：这篇论文解决了什么问题？提出了什么方法？取得了什么结果？）

【逻辑推导】
还原作者的思考路径，按三步结构讲解：
**背景**：之前的方法为什么解决不好这个问题？核心瓶颈在哪？
**破局**：作者的核心直觉或洞察是什么？为什么这个思路能突破瓶颈？
**拆解**：方法分几步实现？请用 1. 2. 3. 简洁列出从输入到输出的关键步骤。

【技术细节】
补充最关键的 1-2 个技术实现细节（如特殊的 Loss 函数、数据增强策略、训练技巧等）。

【局限性】
指出该方法的潜在局限、适用边界或未解决的问题。

【专业名词解释】
解释论文中出现的 2-3 个核心专业术语（面向刚进入该领域的读者）。"""

    try:
        return _call_api(prompt, llm_config)
    except Exception as e:
        return f"⚠️ 摘要生成失败：{e}"
