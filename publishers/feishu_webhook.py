"""
飞书群消息推送模块（Webhook Bot）

推送策略：
  1. 先发一张「今日摘要卡片」，列出所有精选论文的标题、评分和一句话理由
     （含知识库文档链接，若有）
  2. 再逐篇发送「论文详情卡片」，包含完整五段式摘要
"""
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

# 飞书卡片 markdown 单元素内容上限（保守取值）
_CARD_CONTENT_LIMIT = 28000


def _post(webhook_url: str, payload: dict, timeout: int = 15):
    resp = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200 or resp.json().get("code", 0) != 0:
        print(f"  [飞书Webhook] 推送异常: {resp.text[:200]}")


def _make_card(header_text: str, content: str, color: str = "blue") -> dict:
    """构造飞书交互卡片。"""
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_text},
                "template": color,
            },
            "elements": [
                {"tag": "markdown", "content": content},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "由 DeepSeek 自动生成 · paper-push-bot",
                        }
                    ],
                },
            ],
        },
    }


def _source_emoji(paper: Dict) -> str:
    src = paper.get("source", "arxiv")
    if src == "huggingface":
        return "🤗"
    if src == "both":
        return "🤗📄"
    return "📄"


def _push_digest_card(
    papers: List[Dict],
    webhook_url: str,
    doc_url: Optional[str],
    timeout: int,
):
    """推送今日摘要总览卡片。"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**共精选 {len(papers)} 篇论文，按相关性排序：**\n"]

    for i, p in enumerate(papers, 1):
        src = _source_emoji(p)
        upvotes = f" 👍{p['upvotes']}" if p.get("upvotes", 0) > 0 else ""
        reason = p.get("score_reason", "")
        code_link = f" · [💻代码]({p['code_url']})" if p.get("code_url") else ""
        lines.append(
            f"**{i}.** {src} ⭐**{p['score']}/10**{upvotes}  \n"
            f"[{p['title']}]({p['url']}){code_link}  \n"
            f"> {reason}\n"
        )

    if doc_url:
        lines.append(f"\n---\n📖 **完整摘要 → [知识库文档]({doc_url})**")

    content = "\n".join(lines)
    payload = _make_card(
        f"📚 {date_str} 论文日报（{len(papers)} 篇）",
        content,
        color="orange",
    )
    _post(webhook_url, payload, timeout)
    print(f"  [飞书Webhook] 摘要总览卡片推送成功")


def _push_paper_card(paper: Dict, idx: int, total: int, webhook_url: str, timeout: int):
    """推送单篇论文详情卡片。"""
    src = _source_emoji(paper)
    upvotes = f" | 👍 {paper['upvotes']}" if paper.get("upvotes", 0) > 0 else ""
    code_link = f" | [💻 代码]({paper['code_url']})" if paper.get("code_url") else ""
    authors = ", ".join(paper.get("authors", [])[:3])
    if len(paper.get("authors", [])) > 3:
        authors += " 等"

    meta = (
        f"{src} ⭐ **{paper['score']}/10** | "
        f"[arXiv]({paper['url']}){code_link}{upvotes}  \n"
    )
    if authors:
        meta += f"👤 {authors}  \n"
    if paper.get("score_reason"):
        meta += f"> {paper['score_reason']}\n\n"

    summary = paper.get("summary_text", "（摘要生成失败）")

    content = meta + "---\n" + summary

    # 超长时截断（极少发生，保险处理）
    if len(content) > _CARD_CONTENT_LIMIT:
        content = content[:_CARD_CONTENT_LIMIT] + "\n\n…（内容过长，请查阅知识库文档）"

    title_short = paper["title"][:60] + ("…" if len(paper["title"]) > 60 else "")
    header = f"[{idx}/{total}] {title_short}"

    payload = _make_card(header, content, color="blue")
    _post(webhook_url, payload, timeout)


def push_to_feishu(
    papers: List[Dict],
    config: dict,
    doc_url: Optional[str] = None,
):
    """
    主入口：推送今日精选论文到飞书群。

    Args:
        papers:   已完成摘要的精选论文列表（按 score 降序）
        config:   完整配置字典
        doc_url:  知识库文档 URL（可为 None）
    """
    webhook_url = config["feishu"]["webhook_url"]
    timeout = config.get("network", {}).get("request_timeout", 15)

    if not webhook_url or "YOUR_" in webhook_url:
        print("[飞书Webhook] 未配置 webhook_url，跳过群消息推送")
        return

    if not papers:
        # 今日无精选论文，推送提示
        payload = _make_card(
            f"📚 {datetime.now().strftime('%Y-%m-%d')} 论文日报",
            "今日暂无与研究方向高度相关的新论文。",
            color="grey",
        )
        _post(webhook_url, payload, timeout)
        return

    print(f"[飞书Webhook] 开始推送，共 {len(papers)} 篇...")

    # 1. 总览卡片
    _push_digest_card(papers, webhook_url, doc_url, timeout)
    time.sleep(0.8)

    # 2. 逐篇详情卡片
    for i, paper in enumerate(papers, 1):
        _push_paper_card(paper, i, len(papers), webhook_url, timeout)
        print(f"  [{i}/{len(papers)}] 已推送: {paper['title'][:50]}...")
        time.sleep(0.8)  # 避免触发飞书限速（建议 ≥ 0.5s）

    print(f"[飞书Webhook] 全部推送完成")
