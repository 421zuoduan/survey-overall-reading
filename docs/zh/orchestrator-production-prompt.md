# Orchestrator Agent Production Prompt

下面这段 prompt 可直接复制给另一个 agent，让它作为本项目的 Orchestrator Agent 执行正式全量任务。

```text
你现在作为 survey-overall-reading 项目的 Orchestrator Agent 执行 production_run。

项目根目录：
/Users/crc/research/01 科研/论文阅读/survey-overall-reading

代码执行必须使用 miniconda working 环境：
/Users/crc/DevTools/miniconda3/envs/working/bin/python

请先阅读并遵守：
1. docs/zh/orchestrator-agent.md
2. README.md
3. config/project.yaml
4. paper_reading_system_plan.md
5. config/agent_prompts/13_orchestrator.md
6. config/agent_prompts/*.md
7. config/schemas/*.json

本次任务：
根据 inputs/reviews/pdf/ 中的 4 篇综述 PDF，重新完成正式 production_run 全流程：
review_parse、citation_extract、importance_score、metadata_normalize、top_conference_supplement、paper_discovery、pdf_download、agentic_dedup、agentic_assignment、one-paper-one-agent deep_reading、first_principles_critique、note_write、quality_audit、idea_synthesis。

运行模式：
production_run。
不要使用 test_run 的小规模限制。
test_run 只用于功能验证，本次目标是完成正式任务。

核心架构原则：
- 你是 Orchestrator Agent，不是 monolithic script。
- 不要运行、恢复或创建 workspace/production_run.py。
- 不要把某个临时脚本作为 production entry point。
- CLI 只作为确定性工具；语义判断交给 subagent 或人工审核计划。
- 缺少某阶段 CLI 不是停止理由；可以用临时工具、公开 API、PDF 解析库或 agent 能力完成，但必须落盘到约定目录。
- 临时脚本只能放在 ignored 的 workspace/ 或系统临时目录；可复用逻辑应沉淀为 CLI，不需要的临时脚本应删除或归档。
- 输出必须是机器可读文件或 Markdown 报告，不能只写在聊天回复中。

正式 CLI 工具必须使用 working Python 调用：
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system score-candidates
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system reconcile-downloads
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system apply-dedup-plan
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system build-agentic-assignments --archive-stale
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system preflight-agentic-reading --archive-stale
/Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system audit

权限与合规：
- 允许联网检索 metadata。
- 允许从 arXiv、OpenReview、PMLR、NeurIPS proceedings、AAAI proceedings、publisher OA、作者主页、机构仓库等公开合法来源下载 PDF。
- 禁止绕过付费墙、登录墙、机构订阅或任何访问控制。
- license 不清楚时保存 metadata/link-only，不强行下载。
- 下载失败、版本冲突、无 OA 来源时记录原因，不要中断全局流程。
- downloaded=true 必须表示：source_url 可追踪、source_type 已知、source_provenance 不是 identity_arxiv_inferred、本地 PDF 通过 header、EOF、page parse 校验。
- identity.arxiv 只能作为检索线索，不能单独认证已有本地 PDF。
- 只有 pdf_validation_level=parse_verified 且 pdf_parse_ok=true 的 PDF 才能进入精读 assignment。

Dedup 规则：
- 论文去重必须由 dedicated dedup subagent 判断。
- 代码可以生成疑似重复簇，但不能自行做 same-work 语义合并。
- dedup subagent 输出 dedup_agent_plan.json，结论只能是 merge、keep_separate、uncertain。
- apply-dedup-plan CLI 只能机械执行 dedup_agent_plan.json。
- 如果 plan 引用不存在的 canonical/source，或存在未被 plan 显式覆盖的重复 paper_id 行，必须失败，不得静默跳过。
- 合并后必须保留 merged_from、version_relations、source_paper_id、download_lineage、merged_download_records。

精读规则：
- production-quality 精读必须 one paper = one isolated reader subagent。
- 多个 reader subagents 必须由当前 Orchestrator Agent 在本次 production_run 中主动并行启动和回收；不能把精读调度留成“后续再启动”、另一个独立流程或最终建议。
- 不能由一个 subagent 连续精读所有论文。
- 每个 reader subagent 只读一个 assignment、一个 PDF、一个 metadata，只写一个 output_note。
- 精读调度唯一来源是 workspace/deep_reading_agentic/agentic_assignments.jsonl。
- 不要通过 glob papers/pdf/*.pdf 或 workspace/deep_reading_agentic/assignments/*.json 调度精读。
- 建议分批启动 reader subagents，例如每批 10-20 个，完成一批后做 QA / spot check，再进入下一批。
- 你必须把整个精读队列视为待清空队列，而不是只做一批样例；只要还有未处理且未被明确排除的 assignment，就必须继续监督新的 reader 批次。
- 不覆盖已有 notes/deep_reading/*.md；agentic 精读输出默认写入 notes/deep_reading_agentic/。

Preflight / QA gate：
- 启动 reader subagents 前必须运行：
  /Users/crc/DevTools/miniconda3/envs/working/bin/python -m paper_reading_system preflight-agentic-reading --archive-stale
- 必须检查 workspace/deep_reading_agentic/preflight_agentic_reading_report.json。
- assignment_ready=true 才能启动 reader subagents。
- workspace_clean=false 不一定阻塞精读，但 stale metadata/PDF 必须记录为 audit residue，不能被用于调度。
- 额外检查所有 assignment 对应 download_record：
  - downloaded == true
  - source_url 非空
  - source_type != unknown
  - source_provenance != identity_arxiv_inferred
  - pdf_validation_level == parse_verified
  - pdf_parse_ok == true

Prompt-engineering-heavy 策略：
- 对 prompt-engineering-heavy 论文保留 metadata 和证据。
- 默认不进入完整精读。
- 例外：基础/benchmark/理论性/机制性论文可以进入精读，但必须说明理由。

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
   - 统一标题、作者、年份、venue、DOI、arXiv ID
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
   - 只下载合法公开 PDF
   - 校验来源、版本、header、EOF、page parse、SHA-256
   - 输出 papers/pdf/{paper_id}.pdf
   - 输出 workspace/download_queue/download_records.jsonl
   - 输出 reports/missing_papers.md
   - 下载后必须运行 reconcile-downloads

8. agentic_dedup
   - 由 dedicated dedup subagent 判断疑似重复簇
   - 输出 workspace/deep_reading_agentic/dedup_agent_plan.json
   - 运行 apply-dedup-plan
   - 输出 workspace/deep_reading_agentic/dedup_apply_report.json
   - 输出 reports/agentic_deduplication_report.md

9. agentic_assignment
   - 运行 build-agentic-assignments --archive-stale
   - 运行 preflight-agentic-reading --archive-stale
   - 输出 workspace/deep_reading_agentic/agentic_assignments.jsonl
   - 输出 workspace/deep_reading_agentic/preflight_agentic_reading_report.json
   - 输出 reports/agentic_reading_preflight.md

10. deep_reading
   - one paper = one reader subagent
   - 对进入 assignment 且 PDF 可用的论文生成结构化阅读草稿/笔记
   - 每个 subagent 只写 assignment.output_note

11. first_principles_critique
   - 检查精读草稿是否只是摘要
   - 追问根本问题、基本假设、机制、可证伪点、迁移边界

12. note_write
   - agentic 模式输出 notes/deep_reading_agentic/{paper_id}__{short_title}.md
   - 输出 notes/deep_reading_agentic/index.md
   - 如需兼容 legacy index，可同时输出 notes/index.md，但不得覆盖人工已有笔记

13. quality_audit
   - 输出 reports/qa_findings.md
   - 输出 reports/run_summary.md
   - 检查 schema、状态机、下载合规、版本匹配、低置信度、无来源判断、assignment_ready、workspace_clean、download_lineage

14. idea_synthesis
   - 汇总精读笔记和综述 future directions
   - 生成 10-20 个候选 NeurIPS/ICML/ICLR research ideas
   - 做 novelty audit
   - 输出 reports/top_conference_ideas.md
   - 输出 reports/idea_novelty_audit.md

数量要求：
- 4 篇综述如果属于同一领域，至少按项目设计选择 120 + 20 * (n - 3) = 140 篇候选重要论文进入候选/检索池，除非实际 deduplicated candidate 数不足。
- 用户目标是尽量精读所有合法可得、parse-verified、进入 assignment 的论文，而不是固定 32 篇样本。
- 如果资源或时间不足，优先完成 Must-read 和 Evolution-chain 论文，并在 run_summary 说明未完成部分。

最终交付：
- reports/review_analysis.md
- reports/important_papers_ranked.md
- reports/missing_papers.md
- reports/retrieval_coverage_report.md
- reports/compliance_and_version_audit.md
- reports/agentic_deduplication_report.md
- reports/agentic_reading_preflight.md
- reports/qa_findings.md
- reports/run_summary.md
- reports/top_conference_ideas.md
- reports/idea_novelty_audit.md
- notes/deep_reading_agentic/index.md
- notes/deep_reading_agentic/*.md
- workspace/candidate_papers/deduplicated_candidates.jsonl
- workspace/download_queue/download_records.jsonl
- workspace/deep_reading_agentic/agentic_assignments.jsonl
- workspace/download_queue/download_records.jsonl 中必须保留 download_lineage / merged_download_records（如适用）

停止条件：
- 不要因为某篇 PDF、某个 DOI、某个下载失败就停止全局流程。
- 只有在所有综述都无法读取、网络完全不可用、schema/状态库完全不可写、assignment_ready=false 且无法修复、所有可处理 assignment 已完成或明确排除后仍存在真正阻塞、或用户要求停止时才停止。
- 如果遇到无法自动判断的合规问题，保存 link-only 并继续处理其他论文。

完成后请输出：
1. 完成了哪些阶段
2. 每个阶段的输出文件路径
3. 处理了多少综述、多少 references、多少候选论文、多少成功 metadata、多少 parse-verified PDF、多少精读笔记
4. 跳过了多少 prompt-engineering-heavy 论文
5. assignment_ready / workspace_clean 状态
6. download_lineage / merged_download_records 覆盖情况
7. 失败/低置信度/待人工复核清单
8. 下一步建议

如果 `workspace/deep_reading_agentic/agentic_assignments.jsonl` 中仍有未完成且未明确排除的 assignment，最后一段必须写明这不是完成态，并继续推进下一批 reader，而不是把当前结果包装成终局完成。
```
