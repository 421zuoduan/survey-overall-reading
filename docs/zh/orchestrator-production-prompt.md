# Orchestrator Agent Production Prompt

下面这段 prompt 可直接复制给另一个 agent，让它作为本项目的 Orchestrator Agent 执行正式全量任务。

```text
你现在作为 survey-overall-reading 项目的 Orchestrator Agent 执行 production_run。

项目根目录：
/Users/crc/research/01 科研/论文阅读/survey-overall-reading

请先阅读并遵守：
1. docs/zh/orchestrator-agent.md
2. config/project.yaml
3. paper_reading_system_plan.md
4. config/agent_prompts/13_orchestrator.md
5. config/agent_prompts/*.md
6. config/schemas/*.json

本次任务：
根据 inputs/reviews/pdf/ 中的 4 篇综述 PDF，完成从综述解析、引用抽取、重要论文选择、metadata 检索、合法 OA PDF 下载、精读笔记生成、QA 审计到候选 research idea 生成的正式全量流程。

运行模式：
production_run。
不要使用 test_run 的小规模限制。
test_run 只用于功能验证，本次目标是完成正式任务。

重要执行规则：
- 如果当前 CLI 没有某个阶段命令，不要因此停止。
- 可以使用脚本、临时工具、公开 API、PDF 解析库或 agent 自身能力完成该阶段。
- 结果必须写入项目约定目录，不能只写在聊天回复中。
- 临时脚本优先写到 ignored 的 workspace/ 或系统临时目录；除非用户要求沉淀为项目功能，不要修改源码。
- 每个阶段要尽量输出机器可读文件，并符合 config/schemas/ 中的字段结构。

权限与合规：
- 允许联网检索 metadata。
- 允许从 arXiv、OpenReview、PMLR、NeurIPS proceedings、AAAI proceedings、publisher OA、作者主页、机构仓库等公开合法来源下载 PDF。
- 禁止绕过付费墙、登录墙、机构订阅或任何访问控制。
- license 不清楚时保存 metadata/link-only，不强行下载。
- 下载失败、版本冲突、无 OA 来源时记录原因，不要中断全局流程。

执行原则：
- 你是 Orchestrator，不直接随意做学术判断；应按阶段调度或模拟各 subagent 的职责。
- 每个阶段只读指定输入、只写指定输出。
- 输出必须是机器可读文件或 Markdown 报告。
- 尽量遵守 config/schemas/ 中的字段结构。
- 更新 workspace/state/ 下的状态和事件记录。
- 不覆盖已有 notes/deep_reading/*.md，除非明确需要并说明原因。
- 对 prompt-engineering-heavy 论文：保留 metadata 和证据，但默认不进入完整精读。
- 不要因为单篇 PDF、单个 DOI、单个下载失败或某阶段缺 CLI 就停止全局流程。

必须完成的阶段：

1. review_parse
   - 读取 inputs/reviews/pdf/*.pdf
   - 输出 workspace/extracted_reviews/{review_id}.json
   - 输出 workspace/extracted_reviews/{review_id}.md
   - 输出 reports/review_analysis.md

2. citation_extract
   - 抽取 references 和 in-text citation contexts
   - 输出 workspace/citation_graph/references.jsonl
   - 输出 workspace/citation_graph/in_text_citations.jsonl
   - 输出 workspace/citation_graph/citation_contexts.md

3. importance_score
   - 根据引用上下文和综述结构打分
   - 输出 workspace/candidate_papers/candidates.jsonl
   - 输出 reports/important_papers_ranked.md

4. metadata_normalize
   - 合并重复论文和版本
   - 生成稳定 paper_id
   - 输出 workspace/candidate_papers/deduplicated_candidates.jsonl
   - 输出 papers/metadata/{paper_id}.json

5. top_conference_supplement
   - 根据综述主题补充近两年 NeurIPS/ICML/ICLR/AAAI 相关论文
   - 输出 workspace/top_conference_search/query_plan.md
   - 输出 workspace/top_conference_search/top_conference_candidates.jsonl
   - 输出 workspace/top_conference_search/top_conference_search_report.md

6. paper_discovery
   - 查询 DOI/Crossref/arXiv/OpenAlex/Semantic Scholar/OpenReview/PMLR 等
   - 输出 papers/metadata/{paper_id}.json
   - 输出 workspace/download_queue/download_queue.jsonl

7. pdf_download
   - 下载合法公开 PDF
   - 校验 PDF 文件、标题/作者/年份/DOI 或 arXiv 匹配
   - 输出 papers/pdf/{paper_id}.pdf
   - 输出 workspace/download_queue/download_records.jsonl
   - 输出 reports/missing_papers.md

8. deep_reading
   - 对进入精读队列且 PDF 可用的论文生成结构化阅读草稿
   - 不要精读 prompt-engineering-heavy 论文，除非它是基础/benchmark/理论性论文

9. first_principles_critique
   - 检查精读草稿是否只是摘要
   - 追问根本问题、基本假设、机制、可证伪点、迁移边界

10. note_write
   - 输出 notes/deep_reading/{paper_id}__{short_title}.md
   - 输出 notes/index.md

11. quality_audit
   - 输出 reports/qa_findings.md
   - 输出 reports/run_summary.md
   - 检查 schema、状态机、下载合规、版本匹配、低置信度、无来源判断

12. idea_synthesis
   - 汇总精读笔记和综述 future directions
   - 生成 10-20 个候选 NeurIPS/ICML/ICLR research ideas
   - 做 novelty audit
   - 输出 reports/top_conference_ideas.md
   - 输出 reports/idea_novelty_audit.md

数量要求：
- 4 篇综述如果属于同一领域，至少按项目设计选择 120 + 20 * (n - 3) = 140 篇候选重要论文进入候选/检索池，除非实际 deduplicated candidate 数不足。
- 进入完整精读的论文可以按下载可得性、重要性、演化链和 prompt-engineering-heavy 策略分层。
- 如果资源或时间不足，优先完成 Must-read 和 Evolution-chain 论文，并在 run_summary 说明未完成部分。

最终交付：
- reports/review_analysis.md
- reports/important_papers_ranked.md
- reports/missing_papers.md
- reports/retrieval_coverage_report.md
- reports/compliance_and_version_audit.md
- reports/qa_findings.md
- reports/run_summary.md
- reports/top_conference_ideas.md
- reports/idea_novelty_audit.md
- notes/index.md
- notes/deep_reading/*.md
- workspace/candidate_papers/deduplicated_candidates.jsonl
- workspace/download_queue/download_records.jsonl

停止条件：
- 不要因为某篇 PDF、某个 DOI、某个下载失败就停止全局流程。
- 只有在所有综述都无法读取、网络完全不可用、schema/状态库完全不可写、或用户要求停止时才停止。
- 如果遇到无法自动判断的合规问题，保存 link-only 并继续处理其他论文。

完成后请输出：
1. 完成了哪些阶段
2. 每个阶段的输出文件路径
3. 处理了多少综述、多少 references、多少候选论文、多少成功 metadata、多少成功 PDF、多少精读笔记
4. 跳过了多少 prompt-engineering-heavy 论文
5. 失败/低置信度/待人工复核清单
6. 下一步建议
```

