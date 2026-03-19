# 个性化论文推送系统

每天从 arXiv RSS 和 Hugging Face Daily Papers 抓取论文，按研究方向筛选，用 DeepSeek 评分和生成中文摘要，再推送到飞书群并写入飞书知识库。

## 功能

- 多源抓取：`arXiv RSS` + `Hugging Face Daily Papers`
- 增量调度：记录上次成功运行时间，按时间窗口抓取，避免每天定时运行时漏文
- 智能筛选：关键词预过滤 + DeepSeek 0-10 相关性评分
- 中文摘要：五段式结构化总结
- 飞书交互：群里发送单张总览候选卡片，回复序号后再入知识库
- 知识库写入：自动创建当日飞书 Wiki / 云文档
- 去重：SQLite 记录已处理论文，避免重复推送
- 重推工具：支持从数据库取高分论文重新推送

## 运行流程

`main.py` 的主流程：

1. 读取 `config.yaml`
2. 计算本次抓取时间窗口
3. 拉取 arXiv / Hugging Face 论文并按时间窗口过滤
4. 合并、去重、关键词过滤
5. 调用 DeepSeek 打分
6. 对达标论文生成摘要和代码链接
7. 向飞书群发送候选总览卡片
8. 轮询群内回复，确定入库论文
9. 写入飞书知识库并发送完成通知
10. 更新运行状态文件和 SQLite 记录

## 安装

```bash
pip install -r requirements.txt
```

## 配置

复制示例配置：

```bash
cp config.yaml.example config.yaml
```

至少需要填写：

- `llm.api_key`
- `feishu.webhook_url`

如果要启用群内交互和知识库写入，还需要填写：

- `feishu.chat_id`
- `feishu.app_id`
- `feishu.app_secret`
- `feishu.wiki_space_id`
- `feishu.wiki_parent_node`

## 配置说明

### 抓取窗口

`fetch` 配置用于支持每天定时运行时的增量抓取：

```yaml
fetch:
  initial_lookback_hours: 48
  overlap_hours: 18
```

含义：

- 首次运行或没有状态文件时，默认回看最近 `48` 小时
- 后续运行会从“上次成功运行时间 - 18小时”开始重叠抓取
- 再结合 SQLite 按 `arxiv_id` 去重，避免因为时间重叠导致重复推送

运行状态保存在：

```text
db/runtime_state.json
```

### Hugging Face 限制

当前 `daily_papers` 接口的 `limit` 最大有效值为 `100`。示例配置已经使用 `100`。

## 飞书知识库初始化

先在飞书开放平台创建自建应用，并开通：

- `wiki:wiki`
- `docx:document`

然后运行：

```bash
py -3 _setup_wiki.py <your_wiki_page_url>
```

它会帮助你填充 `wiki_space_id` 和 `wiki_parent_node`。

## 日常运行

### 主流程

Windows:

```bash
run_daily.bat
```

或直接运行：

```bash
py -3 main.py
```

### 重推数据库中的高分论文

例如只取前 3 篇进行重推：

```bash
py -3 repush.py --limit 3 --poll-timeout 10
```

参数说明：

- `--limit`：只重推前 N 篇高分论文，`0` 表示不限制
- `--poll-timeout`：群内回复等待时间，单位分钟

## 定时任务建议

建议每天 `08:00` 启动：

- 论文抓取、评分、摘要生成通常需要一段时间
- 正常情况下接近 `09:00` 可以完成推送

当前逻辑已经针对这个场景做了补强：

- 不是只看“今天快照”
- 而是按“上次成功运行时间 + 重叠窗口”抓取

这能显著降低 `3月18日 09:00` 之后到当天深夜新增论文在 `3月19日` 运行时被漏掉的风险。

## 项目结构

```text
paper_push/
├── main.py
├── repush.py
├── config.yaml.example
├── _setup_wiki.py
├── run_daily.bat
├── sources/
│   ├── arxiv_source.py
│   └── hf_source.py
├── pipeline/
│   ├── keyword_filter.py
│   ├── llm_scorer.py
│   ├── summarizer.py
│   └── dedup.py
├── publishers/
│   ├── feishu_webhook.py
│   └── feishu_docs.py
└── db/
    ├── papers.db
    └── runtime_state.json
```

## 说明

- `main.py` 用于日常自动运行
- `repush.py` 用于从本地数据库中重推已评分论文
- 飞书群当前采用“单张总览候选卡片 + 群回复选择”的交互方式
- 写入飞书文档前会清理 Markdown 标记，避免 `**` 之类的格式残留
