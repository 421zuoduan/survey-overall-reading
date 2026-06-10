# Survey Overall Reading 中文使用文档

## 1. 项目简介

Survey Overall Reading 是一个“从综述到重要论文精读”的本地优先工作流项目。目标是帮助使用者从综述论文出发，整理候选论文、计算重要性分数、生成可追溯的精读笔记模板，并为后续研究 idea 提炼保留结构化证据。

当前版本是早期离线核心实现，重点覆盖：

- 候选论文 JSONL 读取与校验
- `paper_id` 稳定生成
- 重要性分数、idea 分数和选择分数计算
- 提示词工程重论文的精读过滤
- 一篇论文一个 Markdown 精读笔记模板
- 本地状态记录
- QA 审计报告

尚未实现自动 PDF 解析、联网论文检索、PDF 下载和完整论文内容精读。

## 2. 环境要求

- Python 3.9 或以上
- 当前离线核心不需要第三方 Python 依赖

在项目根目录运行：

```bash
python3 -m paper_reading_system --help
```

如果项目被安装为包，也可以使用：

```bash
paper-reading --help
```

## 3. 目录说明

```text
config/
  project.yaml              项目配置
  review_inputs.yaml        综述输入配置占位
  schemas/                  JSON schema
  agent_prompts/            各阶段 agent prompt

inputs/reviews/pdf/         放置综述 PDF，本目录被 Git 忽略
inputs/reviews/metadata/    放置 DOI、arXiv、网页链接等 metadata，本目录被 Git 忽略

workspace/                  运行时状态、缓存和中间产物，本目录被 Git 忽略
papers/pdf/                 下载的论文 PDF，本目录被 Git 忽略
notes/deep_reading/         生成的精读笔记，本目录被 Git 忽略
reports/                    生成的报告，本目录被 Git 忽略

paper_reading_system/       Python 源码
tests/                      单元测试
```

## 4. 快速开始

### 4.1 初始化目录

```bash
python3 -m paper_reading_system init
```

### 4.2 放入综述 PDF

把综述 PDF 放入：

```text
inputs/reviews/pdf/
```

如果你有 DOI、arXiv、HTML 链接或人工整理的 metadata，可以放入：

```text
inputs/reviews/metadata/
```

注意：当前版本不会自动解析 PDF，需要先人工或后续模块生成候选论文 JSONL。

### 4.3 准备候选论文 JSONL

候选文件默认路径：

```text
workspace/candidate_papers/candidates.jsonl
```

每一行是一篇候选论文。例如：

```json
{"identity":{"title":"Attention Is All You Need","authors":["Ashish Vaswani"],"year":2017,"venue":"NeurIPS","arxiv":"1706.03762"},"candidate_source":["review_citation"],"raw_scores":{"cross_review_recurrence":0.9,"structural_centrality":0.95,"citation_context_strength":1.0,"foundational_or_benchmark_role":1.0},"idea_scores":{"evolution_chain_position":1.0,"methodological_transferability":1.0}}
```

### 4.4 评分候选论文

```bash
python3 -m paper_reading_system score-candidates
```

输出包括：

```text
workspace/candidate_papers/scored_candidates.jsonl
reports/important_papers_ranked.md
```

### 4.5 生成精读笔记模板

```bash
python3 -m paper_reading_system scaffold-notes
```

输出包括：

```text
notes/deep_reading/
notes/index.md
```

已有精读笔记默认不会被覆盖。只有你明确想重新生成时才使用：

```bash
python3 -m paper_reading_system scaffold-notes --force
```

`notes/index.md` 是自动生成索引，可能在每次 scaffold 时刷新。手工精读内容应写在 `notes/deep_reading/*.md` 中。

### 4.6 运行 QA 审计

```bash
python3 -m paper_reading_system audit
```

输出：

```text
reports/qa_findings.md
```

如果笔记中还有 `待补充` 占位文本，audit 会报告提醒。这是正常行为，用于标记尚未完成精读的笔记。

## 5. 提示词工程重论文策略

如果一篇论文的大部分贡献来自提示词模板、手工提示词搜索、提示词措辞技巧、任务特定 instruction phrasing，而不是新方法、新数据集、新 benchmark、理论贡献或可迁移机制，本项目默认不对它做完整精读。

这类论文会：

- 保留 metadata 和证据
- 在排序报告中显示跳过精读原因
- 不生成 `notes/deep_reading/*.md` 精读笔记

标记方式一：

```json
{"identity":{"title":"Prompt Tricks for Everything","authors":["A. Author"],"year":2024},"tags":["prompt_engineering_heavy"],"raw_scores":{"citation_context_strength":0.8}}
```

标记方式二：

```json
{"identity":{"title":"Prompt Tricks for Everything","authors":["A. Author"],"year":2024},"raw_scores":{"citation_context_strength":0.8,"prompt_engineering_dependency":0.9}}
```

当 `raw_scores.prompt_engineering_dependency >= 0.70` 时，会默认跳过精读。

例外情况：如果该论文定义了重要 benchmark、提出理论框架、或是领域不可替代的基础论文，可以不要标记为 `prompt_engineering_heavy`，或在后续流程中单独保留。

## 6. 测试

运行全部单元测试：

```bash
python3 -m unittest discover -s tests -v
```

当前测试覆盖：

- `paper_id` 生成
- 候选输入校验
- 重要性评分
- 提示词工程重论文过滤
- 精读笔记生成
- 已有笔记不覆盖
- 重复候选检测
- 状态机禁止回退
- CLI 工作流

## 7. Git 与本地文件

`.gitignore` 已忽略本地数据和生成产物，包括：

- 综述 PDF
- 下载论文 PDF
- `workspace/`
- `notes/`
- `reports/`
- SQLite 状态库
- Python 缓存和构建产物

因此 GitHub 仓库默认只保留源码、配置、prompt、schema、测试和文档。

## 8. 当前限制

当前项目还没有自动完成以下步骤：

- 从 PDF 中抽取综述结构
- 自动抽取 references 和 in-text citations
- 联网检索论文 metadata
- 下载 open-access PDF
- 自动阅读 PDF 并填充完整精读内容
- 自动生成和审计 research idea

这些能力已经在 `config/agent_prompts/` 和 `paper_reading_system_plan.md` 中保留了设计入口，后续可以逐步实现。

