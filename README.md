# 个性化论文推送系统

每日自动从 arXiv + HuggingFace Daily Papers 抓取论文，用 DeepSeek 按研究方向评分筛选，生成中文摘要，推送到飞书群消息并写入飞书知识库。

## 功能

- **多源抓取**：arXiv RSS（cs.CV / cs.AI / cs.LG / cs.CL / cs.RO）+ HuggingFace Daily Papers
- **智能筛选**：关键词预过滤 → DeepSeek 0-10 相关性评分 → 阈值过滤（默认 ≥6）
- **中文摘要**：五段式结构（要点 / 逻辑 / 技术细节 / 局限性 / 术语解释）
- **飞书推送**：群消息总览卡片 + 逐篇详情卡片
- **知识库文档**：在飞书 Wiki 自动创建当日日报文档
- **去重**：SQLite 记录已处理论文，避免次日重复

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`，填写：
- `llm.api_key`：[DeepSeek API Key](https://platform.deepseek.com/)
- `feishu.webhook_url`：飞书群自定义机器人 Webhook URL

### 3. 配置飞书知识库（可选）

在[飞书开放平台](https://open.feishu.cn/)创建自建应用，开通 `wiki:wiki` 和 `docx:document` 权限，然后运行：

```bash
py -3 _setup_wiki.py <your_wiki_page_url>
```

脚本会自动写入 `wiki_space_id` 和 `wiki_parent_node`。

### 4. 运行

```bash
# Windows
run_daily.bat

# Linux / macOS
PYTHONUTF8=1 python main.py
```

## 自动化调度

### Windows 任务计划程序

将 `run_daily.bat` 添加到任务计划，每天早上 9 点执行。

### GitHub Actions

Fork 本仓库后，在 `Settings → Secrets` 中添加以下 Secrets：

| Secret 名称 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL |
| `FEISHU_APP_ID` | 飞书应用 App ID（知识库功能，可选）|
| `FEISHU_APP_SECRET` | 飞书应用 App Secret（可选）|
| `FEISHU_WIKI_SPACE_ID` | 知识库空间 ID（可选）|
| `FEISHU_WIKI_PARENT_NODE` | 父节点 token（可选）|

默认每周一至周五北京时间 09:00 自动运行，也可在 Actions 页面手动触发。

## 项目结构

```
paper_push/
├── main.py                    # 主入口
├── config.yaml.example        # 配置示例
├── _setup_wiki.py             # 飞书 Wiki 配置向导
├── run_daily.bat              # Windows 启动脚本
├── sources/
│   ├── arxiv_source.py        # arXiv RSS 抓取
│   └── hf_source.py           # HuggingFace Daily Papers 抓取
├── pipeline/
│   ├── keyword_filter.py      # 关键词预过滤
│   ├── llm_scorer.py          # DeepSeek 批量评分
│   ├── summarizer.py          # 中文摘要生成
│   └── dedup.py               # SQLite 去重
├── publishers/
│   ├── feishu_webhook.py      # 飞书群消息推送
│   └── feishu_docs.py         # 飞书知识库文档写入
└── .github/workflows/
    └── daily_push.yml         # GitHub Actions 定时任务
```

## 自定义研究方向

编辑 `config.yaml` 中的 `research_profile` 部分，修改 `directions`（用于 LLM 评分提示词）和 `keywords`（用于关键词预过滤）。
