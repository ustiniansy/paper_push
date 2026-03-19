"""
飞书群消息推送模块（Webhook Bot + App Bot 交互）

推送策略：
  - 发送「今日摘要卡片」，列出所有精选论文的标题、评分和一句话理由

交互式选择（App Bot）：
  - send_candidate_card(): 通过 App Bot 发送候选列表到群
  - poll_user_reply(): 轮询群消息，解析用户回复的序号
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

from publishers.feishu_docs import _get_token, FEISHU_BASE

# 飞书卡片 markdown 单元素内容上限（保守取值）
_CARD_CONTENT_LIMIT = 28000

def _post(webhook_url: str, payload: dict, timeout: int = 15):
    resp = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200 or resp.json().get("code", 0) != 0:
        print(f"  [飞书Webhook] 推送异常: {resp.text[:200]}")


def _post_app_message(
    token: str,
    chat_id: str,
    msg_type: str,
    content: dict,
    timeout: int = 15,
) -> bool:
    resp = requests.post(
        f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        },
        timeout=timeout,
    )
    data = resp.json()
    if data.get("code", -1) != 0:
        print(f"[飞书Bot] 消息发送失败: {data.get('msg', data)}")
        return False
    return True


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
        reason_line = f"> {reason}\n" if reason else ""
        lines.append(
            f"**{i}.** {src} ⭐**{p['score']}/10**{upvotes}  \n"
            f"[{p['title']}]({p['url']}){code_link}  \n"
            f"{reason_line}"
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

    # 总览卡片（仅推送一张）
    _push_digest_card(papers, webhook_url, doc_url, timeout)

    print(f"[飞书Webhook] 总览卡片推送完成")


# ── App Bot 交互式选择 ─────────────────────────────────────────

def _parse_indices(text: str, total: int) -> Optional[List[int]]:
    """
    解析用户回复的序号文本。
    支持: "1,3,5-8", "1、2、3", "1 2 3", "all", "0"(取消), 空白=None(无效)
    返回 0-based 索引列表，取消返回空列表，无效返回 None。
    """
    text = text.strip().lower()
    if not text:
        return None
    if text == "0":
        return []
    if text in ("all", "全部", "全选"):
        return list(range(total))

    # 统一分隔符：顿号→逗号，空格→逗号
    import re
    text = text.replace("、", ",").replace("，", ",")
    text = re.sub(r"\s+", ",", text)

    indices = set()
    try:
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                lo, hi = part.split("-", 1)
                for n in range(int(lo), int(hi) + 1):
                    if 1 <= n <= total:
                        indices.add(n - 1)
            else:
                n = int(part)
                if 1 <= n <= total:
                    indices.add(n - 1)
    except (ValueError, TypeError):
        return None

    return sorted(indices) if indices else None


def send_candidate_card(papers: List[Dict], config: dict) -> Optional[str]:
    """
    通过 App Bot 发送候选论文列表卡片到飞书群。
    返回 message_id（用于后续轮询定位），失败返回 None。
    """
    chat_id = config["feishu"].get("chat_id", "")
    if not chat_id:
        return None

    try:
        token = _get_token(config)
    except Exception as e:
        print(f"[飞书Bot] 获取 token 失败: {e}")
        return None

    # 构造候选列表文本，保持与日报总览一致的风格
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**共精选 {len(papers)} 篇论文，按相关性排序：**\n"]
    for i, p in enumerate(papers, 1):
        src = _source_emoji(p)
        upvotes = f" 👍{p['upvotes']}" if p.get("upvotes", 0) > 0 else ""
        reason = p.get("score_reason", "")
        lines.append(
            f"**{i}.** {src} ⭐**{p['score']}/10**{upvotes}  \n"
            f"{p['title'][:70]}  \n"
            f"> {reason}\n"
        )
    lines.append("\n---")
    lines.append("💡 **请选择要写入知识库的论文：** 回复 `1,3,5-8`、`all`（全选）或 `0`（取消）")
    lines.append("⏰ **10 分钟内未回复将自动全选**")

    content = "\n".join(lines)
    card = {
        "header": {
            "title": {"tag": "plain_text", "content": f"📚 {date_str} 论文日报（{len(papers)} 篇）"},
            "template": "orange",
        },
        "elements": [
            {"tag": "markdown", "content": content},
        ],
    }

    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }

    try:
        resp = requests.post(
            f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if data.get("code", -1) != 0:
            print(f"[飞书Bot] 发送候选卡片失败: {data.get('msg', data)}")
            return None
        msg_id = data["data"]["message_id"]
        print(f"[飞书Bot] 候选卡片已发送 (message_id={msg_id})")
        return msg_id
    except Exception as e:
        print(f"[飞书Bot] 发送候选卡片异常: {e}")
        return None


def poll_user_reply(
    config: dict,
    total: int,
    timeout_minutes: int = 60,
    poll_interval: int = 5,
) -> List[int]:
    """
    轮询飞书群消息，等待用户回复序号。
    返回 0-based 索引列表。超时默认全选。
    """
    chat_id = config["feishu"].get("chat_id", "")
    token = _get_token(config)
    send_ts = str(int(time.time()))
    deadline = time.time() + timeout_minutes * 60

    # 获取 bot 自身的 open_id，用于过滤 bot 自己的消息
    bot_id = None
    try:
        resp = requests.get(
            f"{FEISHU_BASE}/bot/v3/info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        bot_data = resp.json()
        if bot_data.get("code") == 0:
            bot_id = bot_data.get("bot", {}).get("open_id")
    except Exception:
        pass

    print(f"[飞书Bot] 等待用户回复（超时 {timeout_minutes} 分钟）...")

    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            resp = requests.get(
                f"{FEISHU_BASE}/im/v1/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "container_id_type": "chat",
                    "container_id": chat_id,
                    "start_time": send_ts,
                    "sort_type": "ByCreateTimeDesc",
                    "page_size": 20,
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("code", -1) != 0:
                continue

            for msg in data.get("data", {}).get("items", []):
                # 跳过 bot 自己的消息
                sender_id = msg.get("sender", {}).get("id", "")
                if bot_id and sender_id == bot_id:
                    continue
                # 只处理文本消息
                if msg.get("msg_type") != "text":
                    continue
                try:
                    body = json.loads(msg.get("body", {}).get("content", "{}"))
                    text = body.get("text", "")
                except (json.JSONDecodeError, AttributeError):
                    continue

                result = _parse_indices(text, total)
                if result is not None:
                    if not result:
                        print("[飞书Bot] 用户回复 0，取消选择")
                    else:
                        print(f"[飞书Bot] 用户选择了 {len(result)} 篇论文")
                    return result

        except Exception as e:
            print(f"[飞书Bot] 轮询异常: {e}")

        # token 可能过期，每 5 分钟刷新
        elapsed = time.time() - (deadline - timeout_minutes * 60)
        if elapsed > 0 and int(elapsed) % 300 < poll_interval:
            try:
                token = _get_token(config)
            except Exception:
                pass

    print(f"[飞书Bot] 超时未回复，默认全选")
    return list(range(total))


def send_confirmation(config: dict, text: str):
    """通过 App Bot 发送文本消息到飞书群。"""
    chat_id = config.get("feishu", {}).get("chat_id", "")
    if not chat_id:
        print(f"[飞书Bot] 未配置 chat_id，跳过确认消息")
        return

    try:
        token = _get_token(config)
    except Exception as e:
        print(f"[飞书Bot] 获取 token 失败，跳过确认消息: {e}")
        return

    try:
        if _post_app_message(token, chat_id, "text", {"text": text}, timeout=15):
            print(f"[飞书Bot] 确认消息已发送")
    except Exception as e:
        print(f"[飞书Bot] 确认消息发送异常: {e}")
