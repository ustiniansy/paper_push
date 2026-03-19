# Paper Push Advice 2.0

## 结论

和最初相比，`paper_push` 已经跨过了最难的第一道坎：

- 不再是 Feishu 私人脚本，而是有 `daily / conference / demo` 子命令的产品雏形
- 已经支持 `markdown / html / telegram / slack / feishu` 多输出
- 已经有本地 demo、截图、GIF、中英文 README、CI、基础测试
- conference monitor 已经是独立能力，不再是日报流程的附属品

这意味着项目已经从“能用”进入了“可以被看到”。

但如果目标是 `1000 star`，接下来决定上限的，不再是“有没有这些功能”，而是下面 4 件事：

1. 结果质量是否稳定到足以让别人长期开着跑
2. 差异化是否强到让别人一眼记住它不是普通 arXiv summarizer
3. 项目是否能给用户可验证的收益，而不是只展示一套漂亮 demo
4. 社区进入门槛是否低到让陌生人愿意试、愿意转发、愿意提 issue

一句话判断：

`paper_push` 现在已经像一个成品 demo，但还没有形成“强口碑型开源产品”的信任闭环和传播闭环。

---

## 当前已经做对的事情

这些部分已经明显加分，短期内不建议推倒重来：

### 1. 首次可见结果已经足够顺滑

现在有：

- `main.py demo`
- 本地 HTML / Markdown 输出
- `output/index.html`
- 稳定的 `latest` 和 `demo` 文件名
- README 中的截图和 GIF

这已经满足“先看到结果，再决定要不要配置”的基本传播条件。

### 2. 输出层已经产品化

现在的 publisher registry 和 capability 抽象是对的。它把你从“特定平台工具”推进到了“论文情报分发引擎”。

这是未来继续加：

- Email
- Notion
- Discord
- JSON / webhook sink
- API server

的基础。

### 3. conference monitor 已经形成差异化雏形

这是项目最有机会打出记忆点的模块。很多人需要“某个 venue 到底放榜了没、今年出了多少、我关心的方向有没有新增”。

和普通论文摘要器相比，这块更少同质化。

### 4. README 和 demo 资产已经明显进步

现在的 README 至少已经具备：

- 语言切换
- demo preview
- screenshot proof
- demo-first quickstart
- command-based mental model

这对于 star 转化已经不是短板了。

---

## 还差什么

下面这些，才是从“不错的项目”走向“千 star 级项目”的关键差距。

## A. 还没有证明“推荐结果真的好”

这是当前最大的缺口。

现在项目展示了：

- 会抓
- 会筛
- 会总结
- 会推送

但还没有系统证明：

- 为什么它筛得准
- 和纯关键词相比好多少
- 和纯 LLM 相比稳定多少
- 漏掉的多不多
- 误推的多不多

对于普通围观用户，截图足够让他点进来；
对于真正会 star、会推荐、会长期用的人，他会问：

- “结果质量到底可靠吗？”
- “这个分数可不可信？”
- “为什么这篇进了，那篇没进？”

### 建议

优先补一个 `quality` 层，而不是继续加功能。

应该新增：

- 推荐理由标准化输出
- 命中的关键词/方向标签
- rule score + llm score 双通道
- 最终分数构成说明
- “未入选原因”最小解释

更进一步，应该加一个可公开展示的小型 benchmark：

- 给 30 到 50 篇论文做人类标注
- 比较 keyword-only / llm-only / hybrid 的 precision
- README 里给一张简单对比表

只要你能拿出“hybrid ranking 相比 keyword-only 明显更准”的证据，项目可信度会大幅提高。

---

## B. 还没有把 conference monitor 打成真正的 headline

现在 conference monitor 已经存在，也有 conference-only 路径。

但它还没有形成那种“别人一听就觉得这个项目有点东西”的 headline strength。

问题在于：

- 还没有 venue coverage 清单
- 还没有 source reliability 说明
- 还没有 conference 历史样例页
- 还没有“released / pending / failed”统一可视化面板
- 还没有把 venue 新增追踪做成足够强的长期价值展示

### 建议

把 conference monitor 升级成 README 里可以单独成立的一节产品：

应该补：

- 支持会议列表和状态矩阵
- 每个 venue 的抓取来源说明
- `supported / best-effort / experimental` 标签
- `released / pending / fetch_failed` 三态展示
- 历史快照或 changelog
- 专门的 conference dashboard 页面

如果这部分做强，它甚至可以单独在标题里出现：

`Paper intelligence + conference release radar for AI researchers`

这比“paper summarizer with LLM”更有辨识度。

---

## C. 还没有形成“团队使用场景”

千 star 项目通常不是只解决作者个人问题，而是让用户联想到：

- 我们组里可以直接用
- 我们团队群可以直接接
- 我们每周情报同步可以用它

现在项目已经支持多输出，但“团队场景包装”还不够强。

### 建议

下一步重点不要再只写“个人日报”，而要加“团队模式”的叙事和能力：

- 每日 digest 面向 team channel 的展示模板
- weekly summary / weekly top papers
- 不同 profile 并行产出
- lab / team preset config 示例
- 多订阅者 / 多 profile 输出目录

最小可做版本：

- 支持 `profiles/` 目录批量运行
- 支持 `main.py daily --profile multimodal --profile agents` 或 profile batch
- 输出 `output/multimodal/`、`output/agents/`
- README 给出 “for labs / for teams” 示例

一旦用户能想到“实验室里两三个方向一起跑”，项目的想象空间就会大很多。

---

## D. 还没有可持续的反馈闭环

现在系统大多还是单向的：

- 抓
- 评
- 推

但高 star 的工具，通常会让用户产生“越用越懂我”的预期。

### 建议

加轻量反馈机制：

- thumbs up / thumbs down
- save / ignore
- why useful / why noisy
- 手动白名单 / 黑名单关键词
- 用户反馈回流到 profile 或 reranker

不用一开始就做复杂在线学习。

v1 只需要：

- 本地反馈文件
- 反馈统计
- 简单 rerank 偏置

只要 README 能写出：

`Supports lightweight human feedback to improve future ranking`

产品层次就立刻会高一截。

---

## E. 还没有“可部署”故事

现在的运行方式主要还是本地脚本。

这没问题，但想冲高 star，最好让用户马上想到：

- 能挂在 GitHub Actions 吗
- 能部署在 VPS / serverless 吗
- 能每天自动跑吗
- 能给团队长期服务吗

### 建议

至少补三种官方运行方式：

1. Local CLI
2. GitHub Actions scheduled run
3. Docker run

其中 `GitHub Actions` 和 `Docker` 的价值最大。

应该新增：

- `Dockerfile`
- `.env.example`
- `docker-compose.yml` 或最小 docker 命令
- GitHub Actions 定时模板
- README deployment section

这会直接提升：

- 可复制性
- 持久运行信心
- 外部贡献者采用率

---

## F. 还没有“数据面”和“状态面”

现在更像一个执行器，而不是一个可观测系统。

长期运行时，用户会自然关心：

- 今天抓了多少
- 从哪个源抓到的
- keyword filter 留下多少
- scoring 后剩多少
- 被推送了多少
- conference 新增多少
- 哪些 source 出错了

### 建议

增加一份结构化 run summary：

- 每次运行生成 `run_summary.json`
- 本地 HTML index 展示 latest run stats
- 按 source 的抓取统计
- 按 stage 的过滤统计
- errors / warnings 汇总

更进一步，可以在 `output/index.html` 里加：

- Last run time
- Papers fetched / selected / published
- Conference venues checked
- Error count

这类“状态面”非常利于截图，也很利于排障。

---

## G. 还缺少更强的 profile 体系

你现在已经有 `multimodal / vision / nlp / agents`，这是对的。

但距离“广泛适用”还差两步：

1. profile 数量和行业覆盖还不够
2. profile 还没有被包装成真正的可共享资产

### 建议

补两层：

#### 第一层：更多官方 preset

至少增加：

- `reasoning`
- `robotics`
- `audio`
- `biology`
- `security`
- `recsys`

#### 第二层：profile 文件化

建议增加：

- `profiles/*.yaml`
- `main.py daily --profile-file profiles/multimodal.yaml`
- `profiles/README.md`

长期来看，这甚至可以发展成社区贡献入口：

- “NLP profile by X”
- “Medical imaging profile by Y”

这会显著提升社区参与感。

---

## H. 还没有 API / machine-readable story

现在输出主要面向人看。

但很多高 star 项目会因为“它还可以接到我自己的系统里”而被更广泛使用。

### 建议

增加：

- `json` output target
- machine-readable digest schema
- stable data contract for selected papers and conference status

这件事投入不高，但收益很大。因为它会让项目从“工具”变成“基础组件”。

README 里可以顺势写：

`Use local HTML for humans, JSON for downstream automation.`

---

## I. 还没有真正的 release discipline

现在功能很多，但如果没有版本节奏和 change narrative，外部用户会觉得项目“看起来一直在变，但不知道哪版稳定”。

### 建议

尽快建立：

- `CHANGELOG.md`
- 语义化 release tag
- `v0.1`, `v0.2`, `v0.3` 明确主题
- 每个 release 的升级说明

推荐版本节奏：

- `v0.1`: local-first paper intelligence
- `v0.2`: conference radar and multi-output delivery
- `v0.3`: deployable workflows and feedback loop
- `v1.0`: stable ranking + team workflows + deployment templates

这会显著提高项目的外部可预期性。

---

## J. 还没有社区协作设计

你已经有 CI、CONTRIBUTING、issue templates，这很好。

但对冲高 star 来说，还可以再前进一步：

- `good first issue`
- `help wanted`
- roadmap project board
- `profiles wanted` / `publishers wanted` / `conference source wanted`

### 建议

把贡献入口拆成三类：

1. 新 profile
2. 新 publisher
3. 新 conference source

这样外部贡献者更容易找到切入点。

---

## 优先级排序

如果从“离 1000 star 还有多远”的角度看，接下来最值钱的不是继续扩功能，而是按下面顺序推进：

### P0：必须尽快做

1. 结果质量解释层
   包括 score breakdown、matched reasons、basic benchmark
2. conference monitor headline 化
   包括 venue coverage、status matrix、dashboard-like page
3. deploy story
   包括 Docker 和 GitHub Actions
4. run summary / observability
   包括 latest stats、JSON summary、error surface

### P1：高价值

5. team workflows
   包括 multi-profile batch、weekly summary
6. profile 文件化和扩容
7. JSON output target
8. lightweight feedback loop

### P2：增长增强项

9. changelog 和 release discipline
10. 更完整的 community contribution taxonomy
11. 更多 publisher，如 email / discord / notion

---

## 如果只做 5 件事

如果你现在只想做最有价值的 5 件事，我建议就是这 5 件：

1. 做 `quality` 层：解释为什么推荐这篇，并用小 benchmark 证明 hybrid ranking 有价值
2. 把 conference monitor 做成真正的 headline dashboard
3. 增加 `Dockerfile + GitHub Actions` 官方部署路径
4. 增加 `run_summary.json` 和 output index 上的运行统计
5. 支持 `json` output 和 batch profile 跑法

这 5 件事做完，项目会从“很好看的研究者工具”明显升级成“有可信度、有扩展性、有团队想象力的情报系统”。

---

## 建议的下一阶段路线图

## Phase A: Trust

目标：证明结果不是花架子。

做：

- score breakdown
- why-selected tags
- benchmark sample set
- run summary

完成标志：

- README 里能展示 ranking 逻辑和质量对比

## Phase B: Differentiation

目标：把 conference radar 打成独立卖点。

做：

- venue matrix
- conference dashboard page
- source reliability labels
- conference history snapshots

完成标志：

- 用户会因为 conference monitor 而记住项目

## Phase C: Deployability

目标：让用户觉得这东西能长期运行。

做：

- Docker
- GitHub Actions schedule
- deployment docs
- `.env` and secret handling guide

完成标志：

- 用户可以 15 分钟内部署定时任务

## Phase D: Team Mode

目标：把个人工具升级成团队工具。

做：

- multi-profile batch
- team digest
- weekly summary
- profile files

完成标志：

- 实验室和团队有直接采用场景

---

## 最后的判断

现在的 `paper_push` 已经不是“从 0 到 1”的问题了。

接下来要解决的是：

- 从 `demo 好看` 到 `结果可信`
- 从 `功能很多` 到 `卖点很强`
- 从 `作者自用` 到 `团队可用`
- 从 `本地脚本` 到 `可部署产品`

如果继续按这个方向推进，它是有机会接近千 star 级别的。

但真正决定上限的，不会是“再加 3 个输出渠道”，而是：

`你能不能证明，这个系统真的能稳定地帮研究者减少信息遗漏，并把高相关论文准时送到合适的地方。`
