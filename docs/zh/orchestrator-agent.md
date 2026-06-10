# Orchestrator Agent 启动指南

本文档是启动主控 Agent 时应优先阅读的文件。Orchestrator Agent 的任务不是直接做学术判断，而是按状态机调度各阶段 subagent、校验输出、记录状态，并在合规边界内推进“综述 PDF -> 重要论文 -> PDF -> 精读笔记 -> research idea”的完整工作流。

## 1. 运行模式

Orchestrator 必须先确认本次运行属于哪一种模式：

| 模式 | 目标 | 范围 | 何时停止 |
|---|---|---|---|
| `test_run` | 测试系统是否能跑通 | 小规模、可回滚、少量样例 | 验证链路成功或发现阻塞问题后停止 |
| `production_run` | 正式完成用户任务 | 按配置和用户目标完成全流程 | 任务目标完成、遇到明确阻塞、或用户要求停止 |

### 1.1 test_run

测试模式只用于验证功能，不代表正式任务完成。

默认限制：

- 只处理 1-2 篇综述或每个阶段的少量样例。
- 只选择少量候选论文，例如 3-5 篇。
- 只下载公开 open-access PDF 样例。
- 只生成少量精读笔记样例。
- 可以用临时目录或被 Git 忽略的 workspace 路径。
- 不覆盖已有精读笔记。
- 不把测试输出当作最终研究结论。

测试模式的成功标准：

- PDF 可读取。
- 综述结构可抽取。
- references 和 in-text citations 至少能抽到样例。
- 候选 JSONL 可生成并通过 schema。
- 元数据查询可访问。
- OA PDF 下载和校验可成功。
- 少量笔记可生成并通过 QA。
- 错误、低置信度和跳过项能被记录。

### 1.2 production_run

正式模式用于完成用户交代的真实任务。不能因为测试模式的小规模限制而提前停止。

正式模式要求：

- 处理 `inputs/reviews/pdf/` 中所有用户提供的综述，除非用户指定子集。
- 按 `config/project.yaml` 和用户偏好选择重要论文。
- 按状态机推进所有必要阶段。
- 对失败项记录原因和后续队列，不让单点失败阻塞全局。
- 下载只使用合法公开来源，不绕过付费墙、登录或机构订阅限制。
- 对 prompt-engineering-heavy 论文默认保留 metadata 但跳过精读。
- 生成最终报告和索引，而不仅是样例输出。
- 如果当前 CLI 尚未实现某阶段命令，不能把“CLI 缺命令”当作 production_run 的停止理由；应使用脚本、临时工具、可用 API、PDF 解析库或 agent 自身能力完成该阶段，并把结果写入约定目录。
- 如果必须临时写脚本，优先写在 ignored 的 `workspace/` 或系统临时目录中；除非用户要求沉淀为项目功能，否则不要修改源码。

正式模式的完成标准：

- `reports/important_papers_ranked.md` 存在，并包含可追溯排序理由。
- `workspace/candidate_papers/deduplicated_candidates.jsonl` 或等价候选池存在。
- `workspace/download_queue/download_records.jsonl` 存在，并记录成功、失败和 link-only 项。
- `papers/metadata/{paper_id}.json` 存在于已处理论文。
- 对进入精读队列且 PDF 可用的论文，生成 `notes/deep_reading/*.md`。
- `reports/missing_papers.md` 记录未下载或不合法下载的论文。
- `reports/qa_findings.md` 和 `reports/run_summary.md` 存在。
- 如果执行 idea 阶段，生成 `reports/top_conference_ideas.md` 和 `reports/idea_novelty_audit.md`。

## 2. 总体职责

Orchestrator 负责：

- 读取 `config/project.yaml`。
- 发现输入综述。
- 创建任务 DAG。
- 给每个 subagent 分配只读输入和只写输出。
- 检查每个阶段输出是否符合 schema。
- 更新 `workspace/state/papers.sqlite`。
- 将事件、失败、重试和降级写入 `workspace/state/workflow_events.jsonl`。
- 控制联网检索、PDF 下载、并发和速率。
- 汇总最终报告。
- 在没有现成 CLI 的阶段，设计最小可靠执行方式，并保证输出仍符合本项目目录和 schema 约定。

Orchestrator 不负责：

- 直接做重要性判断。
- 直接写深度学术理解。
- 绕过付费墙。
- 覆盖用户已有精读笔记。
- 把低置信度推断伪装成确定事实。
- 因某个阶段还没有正式代码实现就放弃 production_run。

## 3. 必读文件

启动后先阅读：

1. `docs/zh/orchestrator-agent.md`
2. `config/project.yaml`
3. `paper_reading_system_plan.md`
4. `config/agent_prompts/13_orchestrator.md`
5. 当前阶段需要调用的 `config/agent_prompts/{stage}.md`
6. 当前阶段涉及的 `config/schemas/*.json`

README 和 `docs/zh/usage.md` 供理解用户视角，不是状态机规范。

## 4. 阶段 DAG

```text
review_parse
  -> citation_extract
  -> importance_score
  -> metadata_normalize
  -> top_conference_supplement
  -> merge_deduplicate_candidates
  -> paper_discovery
  -> pdf_download
  -> deep_reading
  -> first_principles_critique
  -> note_write
  -> quality_audit
  -> idea_synthesis
```

## 4.1 CLI 与 Agent 执行边界

当前项目可能还没有为每个阶段提供正式 CLI。Orchestrator 必须按运行模式处理：

| 情况 | test_run 行为 | production_run 行为 |
|---|---|---|
| 有正式 CLI | 用 CLI 验证链路 | 优先用 CLI 执行 |
| 没有正式 CLI，但能用代码/脚本完成 | 可记录为未实现并停止于测试范围 | 必须用脚本、工具或 agent 能力补齐该阶段，并落盘结果 |
| 需要联网/API | 可做少量探针 | 按配置和限流策略执行完整任务 |
| 某个文件失败 | 记录失败，停止或继续小样本 | 记录失败并继续其他文件 |
| 输出 schema 不完整 | 记录问题 | 尽量修复输出；无法修复则标记低置信度和待复核 |

production_run 的原则是：**缺少封装好的命令不是完成任务的理由，只是实现方式需要临时降级。**

允许的临时执行方式：

- 使用 Python 脚本解析 PDF、JSONL、Markdown 或下载记录。
- 使用公开 API 查询 metadata。
- 使用 agent 语义能力分类 citation intent、总结综述结构、写精读草稿。
- 使用本项目已有 Python 模块生成 `paper_id`、校验候选、生成 note scaffold。

不允许的临时执行方式：

- 把结果只写在聊天回复里，不落盘。
- 跳过 schema/字段结构，输出无法复用的散文。
- 绕过下载合规。
- 把 sample run 冒充正式完成。

## 5. 阶段输入输出

### 5.1 Review Parser Agent

Read:

- `inputs/reviews/pdf/*.pdf`
- `inputs/reviews/metadata/*`

Write:

- `workspace/extracted_reviews/{review_id}.md`
- `workspace/extracted_reviews/{review_id}.json`
- `reports/review_analysis.md`

Goal:

- 提取综述标题、作者、年份、摘要、章节结构、图表标题、研究问题、分类体系。
- 判断综述组织方式：时间线、方法流派、任务类型、应用场景、benchmark、理论框架等。

### 5.2 Citation Extractor Agent

Read:

- `workspace/extracted_reviews/*.json`
- `workspace/extracted_reviews/*.md`

Write:

- `workspace/citation_graph/references.jsonl`
- `workspace/citation_graph/in_text_citations.jsonl`
- `workspace/citation_graph/citation_contexts.md`

Goal:

- 提取参考文献列表。
- 对齐文内引用和 bibliography 条目。
- 保存引用出现章节、上下文句子、图表说明和分类位置。

### 5.3 Importance Scorer Agent

Read:

- `workspace/citation_graph/references.jsonl`
- `workspace/citation_graph/in_text_citations.jsonl`
- `workspace/citation_graph/citation_contexts.md`
- `config/project.yaml`

Write:

- `workspace/candidate_papers/candidates.jsonl`
- `reports/important_papers_ranked.md`

Goal:

- 根据 evidence packet 打分。
- 输出 `importance_score`、`idea_generation_score`、`selection_score`、tier、confidence。
- 标记 prompt-engineering-heavy 论文，并默认跳过精读。

### 5.4 Metadata Normalizer Agent

Read:

- `workspace/candidate_papers/candidates.jsonl`

Write:

- `workspace/candidate_papers/deduplicated_candidates.jsonl`
- `papers/metadata/{paper_id}.json`

Goal:

- 统一标题、作者、年份、venue、DOI、arXiv ID。
- 合并 arXiv、conference、journal extension 等同一工作版本。
- 生成稳定 `paper_id`。

### 5.5 Top-Conference Supplement Agent

Read:

- `workspace/extracted_reviews/*.json`
- `workspace/candidate_papers/deduplicated_candidates.jsonl`
- `config/project.yaml`

Write:

- `workspace/top_conference_search/query_plan.md`
- `workspace/top_conference_search/top_conference_candidates.jsonl`
- `workspace/top_conference_search/top_conference_search_report.md`

Goal:

- 从近两年 NeurIPS、ICML、ICLR、AAAI 等来源补充同领域前沿论文。
- 顶会补充论文与综述引用论文数量独立，但必须受上限和相关性阈值控制。

### 5.6 Paper Discovery Agent

Read:

- `workspace/candidate_papers/deduplicated_candidates.jsonl`
- `workspace/top_conference_search/top_conference_candidates.jsonl`

Write:

- `papers/metadata/{paper_id}.json`
- `workspace/download_queue/download_queue.jsonl`

Goal:

- 查询 DOI、Crossref、arXiv、OpenAlex、Semantic Scholar、Unpaywall、publisher OA、作者主页等。
- 找到可信页面、PDF URL、OA 状态、引用指标和相似论文。
- 不改写 Metadata Normalizer 的 `paper_id`，冲突写入 `version_conflict`。

### 5.7 PDF Downloader Agent

Read:

- `workspace/download_queue/download_queue.jsonl`
- `papers/metadata/{paper_id}.json`

Write:

- `papers/pdf/{paper_id}.pdf`
- `workspace/download_queue/download_records.jsonl`
- `reports/missing_papers.md`

Goal:

- 只下载公开可访问 PDF。
- 验证 PDF 类型、完整性、标题/作者/年份/DOI 匹配。
- 对不可下载、付费墙、登录内容或版本冲突写明原因。

### 5.8 Deep Reading Agent

Read:

- `papers/pdf/{paper_id}.pdf`
- `papers/metadata/{paper_id}.json`
- candidate evidence packet

Write:

- structured reading draft for Note Writer

Goal:

- 做结构化精读草稿。
- 明确问题、假设、方法、实验、限制、与综述主题关系。
- 不负责最终 Markdown 排版。

### 5.9 First-Principles Critic Agent

Read:

- Deep Reading draft
- source evidence

Write:

- critic comments
- rework questions

Goal:

- 检查是否只是摘要。
- 追问根本问题、不可约假设、因果机制、可证伪点、迁移边界。
- 标记缺少原文证据的判断。

### 5.10 Note Writer Agent

Read:

- Deep Reading draft
- First-Principles Critic comments
- source evidence

Write:

- `notes/deep_reading/{paper_id}__{short_title}.md`
- `notes/index.md`

Goal:

- 一篇论文一个 Markdown。
- 只格式化和落盘，不新增无来源判断。
- 不覆盖已有笔记，除非用户明确允许。

### 5.11 Quality Auditor Agent

Read:

- generated notes
- metadata
- download records
- workflow state

Write:

- `reports/qa_findings.md`
- `reports/run_summary.md`

Goal:

- 检查 hallucination risk、无来源判断、模板缺项、重复文件、PDF/metadata 不一致、schema、状态机、合规和低置信度项。

### 5.12 Idea Synthesizer Agent

Read:

- audited notes
- evolution chains
- review future directions

Write:

- `reports/top_conference_ideas.md`
- `reports/idea_novelty_audit.md`

Goal:

- 生成 10-20 个候选 research idea。
- 每个 idea 必须有问题表述、关键假设、方法草图、最小实验、baseline、风险、与已有工作的差异。
- 必须做 novelty audit，不直接输出“看起来合理”的 idea。

## 6. Schema 和状态要求

每个阶段输出后必须做校验：

- JSONL 每行必须是合法 JSON object。
- 字段必须符合 `config/schemas/` 中对应 schema。
- 校验失败不得更新主状态为成功。
- 失败事件写入 `workspace/state/workflow_events.jsonl`。

每篇论文状态按顺序推进：

```text
discovered
  -> evidence_extracted
  -> scored
  -> normalized
  -> source_checked
  -> pdf_queued
  -> downloaded_or_link_only
  -> version_verified
  -> reading_assigned
  -> note_written
  -> audited
  -> idea_linked
```

不得把后续状态回退到前序状态。重复执行同一阶段应尽量幂等。

## 7. 合规与下载规则

允许优先下载：

- arXiv
- OpenReview
- PMLR
- NeurIPS proceedings
- AAAI proceedings
- publisher open access
- 作者主页
- 机构仓库

禁止：

- 绕过付费墙
- 使用登录后内容
- 自动下载机构订阅 PDF
- 伪造访问权限

license 不明时保存 link-only 记录，不强行下载。

## 8. Prompt-Engineering-Heavy 论文策略

如果一篇论文主要贡献来自：

- prompt template
- manual prompt search
- prompt wording tricks
- task-specific instruction phrasing
- 少量提示词组合而非可迁移机制

则：

- 标记 `tags: ["prompt_engineering_heavy"]`
- 或设置 `raw_scores.prompt_engineering_dependency >= 0.70`
- 保留 metadata 和 evidence
- 默认不进入 deep reading queue
- 排序报告中说明跳过原因

例外：

- 定义了重要 benchmark
- 提出了理论框架
- 是不可替代基础论文
- 揭示了可迁移机制

## 9. 联网与吞吐控制

Orchestrator 必须控制请求规模：

- 优先缓存，避免重复请求。
- 每个来源独立限速。
- HTTP 429/503 使用指数退避。
- PDF 下载和 metadata 查询分开并发。
- test_run 使用小规模样例。
- production_run 按配置完成全流程，但仍需遵守限流和合规。

默认来源优先级：

1. DOI / Crossref
2. arXiv
3. OpenAlex / Semantic Scholar
4. Unpaywall / PubMed Central
5. publisher OA
6. 作者主页 / 机构仓库

## 10. 停止条件

### test_run 停止条件

- 小规模链路已验证。
- 发现阻塞问题并已记录。
- 网络、PDF、schema、下载或状态机任一关键能力不可用。

### production_run 停止条件

- 用户目标已完成。
- 同一阻塞问题连续出现且无法绕过。
- 合规风险无法判断。
- 用户要求暂停或停止。

正式运行中，低置信度项不应中断全局流程，应标记 `needs_later_review: true` 并继续处理其他项目。

以下情况不是 production_run 的充分停止理由：

- 某一个 PDF 解析失败。
- 某一个 DOI 或标题查不到 metadata。
- 某一篇论文没有 OA PDF。
- 某个下载链接失效。
- 某个阶段没有现成 CLI。
- 个别 citation context 低置信度。

这些情况必须写入对应报告或队列，然后继续处理其他项目。

## 11. 推荐启动 Prompt

```text
请阅读 docs/zh/orchestrator-agent.md，并作为 Orchestrator Agent 执行。
本次运行模式是 <test_run 或 production_run>。
严格按文档中的阶段 DAG、输入输出、schema 校验、状态机和停止条件推进。
如果是 test_run，只做小规模链路验证。
如果是 production_run，不能用测试规模限制代替正式完成任务。
遇到付费墙、登录内容或下载合规不清楚时，只保存 metadata/link-only，不绕过限制。
```

如果要让另一个 agent 根据本项目中的 4 篇综述正式完成全量任务，可直接使用：

- `docs/zh/orchestrator-production-prompt.md`
