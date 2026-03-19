"""
飞书知识库文档写入模块（Docs API + Wiki API）

前置条件：
  1. 在飞书开放平台创建「企业自建应用」
  2. 开通权限：wiki:wiki（读写）、docx:document（读写）
  3. 将应用添加为目标知识库空间的「协作者」
  4. 在 config.yaml 中填写 app_id, app_secret, wiki_space_id, wiki_parent_node

文档结构（每日自动创建一个新节点）：
  📚 YYYY-MM-DD 论文日报（N篇）
    ├── 摘要信息行
    ├── ── 分割线 ──
    ├── [一] 论文标题
    │    ├── 来源 | 评分 | 链接
    │    ├── 评分理由
    │    ├── 完整五段式摘要
    │    └── ── 分割线 ──
    └── ...（重复）
"""
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

FEISHU_BASE = "https://open.feishu.cn/open-apis"

# 每次 create children 请求最多 50 个 block
_BLOCK_BATCH = 50
# 单个 text_run 内容上限（保守取值）
_TEXT_RUN_LIMIT = 2000


# ── Token ────────────────────────────────────────────────────

def _get_token(config: dict) -> str:
    """获取 tenant_access_token。"""
    resp = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": config["feishu"]["app_id"],
            "app_secret": config["feishu"]["app_secret"],
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Block 构造 ────────────────────────────────────────────────

def _text_block(content: str, bold: bool = False) -> dict:
    style: dict = {}
    if bold:
        style["bold"] = True
    return {
        "block_type": 2,
        "text": {
            "elements": [
                {"text_run": {"content": content, "text_element_style": style}}
            ]
        },
    }


def _heading_block(content: str, level: int = 2) -> dict:
    """level: 1=heading1(block_type 3), 2=heading2(4), 3=heading3(5)"""
    block_type = 2 + level
    key = f"heading{level}"
    return {
        "block_type": block_type,
        key: {"elements": [{"text_run": {"content": content}}]},
    }


def _divider_block() -> dict:
    return _text_block("─" * 40)


def _split_text(text: str, max_len: int = _TEXT_RUN_LIMIT) -> List[str]:
    """将长文本切分为不超过 max_len 的段落列表。"""
    chunks = []
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut <= 0:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def _strip_markdown(text: str) -> str:
    """Convert markdown-ish LLM output to plain text for Feishu doc blocks."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return text.strip()


def _build_paper_blocks(paper: Dict, idx: int) -> List[dict]:
    """为单篇论文构建 Feishu 文档 Block 列表。"""
    blocks = []

    # 标题
    src_tag = "🤗" if paper.get("source") == "huggingface" else "📄"
    blocks.append(_heading_block(f"{idx}. {paper['title']}", level=2))

    # 元信息行
    upvotes = f" | 👍 {paper['upvotes']}" if paper.get("upvotes", 0) > 0 else ""
    code = f" | 💻 {paper['code_url']}" if paper.get("code_url") else ""
    meta = (
        f"{src_tag} 评分 {paper['score']}/10{upvotes}"
        f" | {paper['url']}{code}"
    )
    blocks.append(_text_block(meta))

    # 评分理由
    if paper.get("score_reason"):
        blocks.append(_text_block(f"📌 {_strip_markdown(paper['score_reason'])}"))

    # 五段式摘要：按【xxx】切分，每段作为独立 block
    summary = _strip_markdown(paper.get("summary_text", ""))
    if summary:
        # 按【section】分割，保留分隔符
        parts = re.split(r"(【[^】]+】)", summary)
        para_buf = []
        for part in parts:
            if re.match(r"【[^】]+】", part):
                # 把之前缓冲的正文内容输出
                if para_buf:
                    para_text = "".join(para_buf).strip()
                    for chunk in _split_text(para_text):
                        blocks.append(_text_block(chunk))
                    para_buf = []
                # 输出段落标题（加粗）
                blocks.append(_text_block(part, bold=True))
            else:
                para_buf.append(part)
        # 最后一段
        if para_buf:
            para_text = "".join(para_buf).strip()
            for chunk in _split_text(para_text):
                blocks.append(_text_block(chunk))

    blocks.append(_divider_block())
    return blocks


# ── Wiki + Docx API ──────────────────────────────────────────

def _create_wiki_node(
    token: str, space_id: str, parent_node: str, title: str
) -> tuple[str, str]:
    """
    在知识库中创建新文档节点。
    返回 (obj_token, node_url)
    """
    resp = requests.post(
        f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes",
        headers=_headers(token),
        json={
            "obj_type": "docx",
            "node_type": "origin",
            "parent_node_token": parent_node,
            "title": title,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"创建 wiki 节点失败: {data}")
    node = data["data"]["node"]
    obj_token = node["obj_token"]
    node_token = node.get("node_token", obj_token)
    node_url = f"https://feishu.cn/wiki/{node_token}"
    return obj_token, node_url


def _get_root_block_id(token: str, doc_token: str) -> str:
    """获取文档根块 ID。"""
    # 新建文档后偶有延迟，最多重试 3 次
    for attempt in range(3):
        resp = requests.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks",
            headers=_headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])
        if items:
            return items[0]["block_id"]
        time.sleep(1.5)
    raise RuntimeError("无法获取文档根块 ID，请检查权限配置")


def _append_blocks(
    token: str, doc_token: str, root_block_id: str, blocks: List[dict]
):
    """分批追加 blocks 到文档根块。"""
    for i in range(0, len(blocks), _BLOCK_BATCH):
        batch = blocks[i : i + _BLOCK_BATCH]
        resp = requests.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{root_block_id}/children",
            headers=_headers(token),
            json={"children": batch},
            timeout=30,
        )
        if resp.status_code != 200 or resp.json().get("code", -1) != 0:
            print(f"  [飞书Docs] 写入 block 异常（批次 {i // _BLOCK_BATCH + 1}）: {resp.text[:300]}")
        time.sleep(0.3)


# ── 公开接口 ─────────────────────────────────────────────────

def create_daily_document(papers: List[Dict], config: dict) -> Optional[str]:
    """
    在飞书知识库中创建当日论文日报文档。

    Args:
        papers: 已完成摘要的精选论文列表
        config: 完整配置字典

    Returns:
        文档 URL（str）；若未配置或出错则返回 None
    """
    fc = config.get("feishu", {})
    required = ["app_id", "app_secret", "wiki_space_id", "wiki_parent_node"]
    missing = [k for k in required if not fc.get(k)]
    if missing:
        print(f"[飞书Docs] 跳过（config.yaml 中未填写: {', '.join(missing)}）")
        return None

    print(f"[飞书Docs] 开始创建知识库文档，共 {len(papers)} 篇...")

    try:
        token = _get_token(config)
        date_str = datetime.now().strftime("%Y-%m-%d")
        title = f"📚 {date_str} 论文日报（{len(papers)}篇）"

        # 1. 创建 wiki 节点
        doc_token, doc_url = _create_wiki_node(
            token, fc["wiki_space_id"], fc["wiki_parent_node"], title
        )
        print(f"  [飞书Docs] 文档已创建: {title}")
        time.sleep(1)  # 等待文档初始化

        # 2. 获取根块 ID
        root_block_id = _get_root_block_id(token, doc_token)

        # 3. 构建所有内容块
        all_blocks: List[dict] = []

        # 文档头部信息
        all_blocks.append(
            _text_block(
                f"📅 {date_str}  |  来源：arXiv + HuggingFace Daily Papers"
                f"  |  共入选 {len(papers)} 篇（评分 ≥ {config['llm']['score_threshold']}）"
            )
        )
        all_blocks.append(_divider_block())

        for i, paper in enumerate(papers, 1):
            all_blocks.extend(_build_paper_blocks(paper, i))

        # 4. 批量写入
        _append_blocks(token, doc_token, root_block_id, all_blocks)

        print(f"[飞书Docs] 文档写入完成 → {doc_url}")
        return doc_url

    except Exception as e:
        print(f"[飞书Docs] 创建文档失败: {e}")
        return None
