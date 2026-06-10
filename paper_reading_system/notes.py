from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .models import CandidatePaper


SECTION_HEADINGS = [
    "1. 基本信息",
    "2. 一句话结论",
    "3. 第一性原理分析",
    "4. 论文结构精读",
    "5. 方法拆解",
    "6. 实验与证据",
    "7. 与综述主线的关系",
    "8. 我的判断",
    "9. 可继续追踪的问题",
    "10. 原文证据索引",
    "11. 顶会 Idea 提炼",
]


def note_filename(candidate: CandidatePaper) -> str:
    short_title = _slug(candidate.identity.title, max_words=8)
    return f"{candidate.paper_id}__{short_title}.md"


def render_note(candidate: CandidatePaper, draft: Mapping[str, str] | None = None) -> str:
    draft = draft or {}
    identity = candidate.identity
    authors = ", ".join(identity.authors)
    evidence_lines = "\n".join(
        f"- {item.dimension}: {item.quote_or_anchor or '待补充'}; {item.reason or '待补充'}"
        for item in candidate.evidence
    )
    if not evidence_lines:
        evidence_lines = "- 待补充"

    return f"""# {identity.title}

## 1. 基本信息

- Title: {identity.title}
- Authors: {authors}
- Year: {identity.year or ""}
- Venue: {identity.venue}
- DOI / arXiv: {identity.doi or identity.arxiv}
- PDF:
- Source review(s): {", ".join(candidate.candidate_source)}
- Importance rank:
- Importance rationale: importance={candidate.importance_score:.4f}; idea={candidate.idea_generation_score:.4f}; selection={candidate.selection_score:.4f}; tier={candidate.tier}; confidence={candidate.confidence}

## 2. 一句话结论

{draft.get("one_sentence_conclusion", "待精读后补充。")}

## 3. 第一性原理分析

### 3.1 根本问题

{draft.get("fundamental_problem", "待补充。")}

### 3.2 基本假设

{draft.get("assumptions", "待补充。")}

### 3.3 必要性

{draft.get("necessity", "待补充。")}

### 3.4 机制解释

{draft.get("mechanism", "待补充。")}

### 3.5 可证伪点

{draft.get("falsification", "待补充。")}

### 3.6 迁移边界

{draft.get("transfer_boundary", "待补充。")}

## 4. 论文结构精读

### 4.1 Introduction

{draft.get("introduction", "待补充。")}

### 4.2 Related Work

{draft.get("related_work", "待补充。")}

### 4.3 Method

{draft.get("method", "待补充。")}

### 4.4 Experiments

{draft.get("experiments", "待补充。")}

### 4.5 Discussion / Limitation

{draft.get("discussion_limitation", "待补充。")}

## 5. 方法拆解

- 输入: {draft.get("method_input", "待补充")}
- 输出: {draft.get("method_output", "待补充")}
- 核心模块: {draft.get("core_modules", "待补充")}
- 训练/推理流程: {draft.get("training_inference", "待补充")}
- 关键公式: {draft.get("key_formulas", "待补充")}
- 复杂度: {draft.get("complexity", "待补充")}

## 6. 实验与证据

- 数据集: {draft.get("datasets", "待补充")}
- Baselines: {draft.get("baselines", "待补充")}
- Metrics: {draft.get("metrics", "待补充")}
- Main results: {draft.get("main_results", "待补充")}
- Ablation: {draft.get("ablation", "待补充")}
- Failure cases: {draft.get("failure_cases", "待补充")}
- 证据是否支撑主张: {draft.get("claim_support", "待补充")}

## 7. 与综述主线的关系

- 在综述中出现的位置: {draft.get("review_position", "待补充")}
- 被综述赋予的角色: {draft.get("review_role", "待补充")}
- 它连接了哪些前后论文: {draft.get("chain_relation", "待补充")}
- 它对领域路线的影响: {draft.get("field_impact", "待补充")}

## 8. 我的判断

- 重要性: {draft.get("importance_judgement", "待补充")}
- 创新性: {draft.get("novelty_judgement", "待补充")}
- 可靠性: {draft.get("reliability", "待补充")}
- 可复现性: {draft.get("reproducibility", "待补充")}
- 值得借鉴的设计: {draft.get("useful_designs", "待补充")}
- 可能被高估的地方: {draft.get("overestimated_points", "待补充")}

## 9. 可继续追踪的问题

- 后续应该读哪些论文: {draft.get("followup_papers", "待补充")}
- 有哪些开放问题: {draft.get("open_questions", "待补充")}
- 可以如何用于自己的研究: {draft.get("research_usage", "待补充")}

## 10. 原文证据索引

{evidence_lines}

## 11. 顶会 Idea 提炼

- 这篇论文暴露的核心 gap: {draft.get("core_gap", "待补充")}
- 可投稿 NeurIPS/ICML/ICLR 的问题表述: {draft.get("top_conference_problem", "待补充")}
- 可能的方法切入: {draft.get("method_angle", "待补充")}
- 最小可行实验: {draft.get("minimal_experiment", "待补充")}
- 需要对比的 baselines: {draft.get("idea_baselines", "待补充")}
- 风险与拒稿点: {draft.get("rejection_risks", "待补充")}
- 与已读演化链的关系: {draft.get("idea_chain_relation", "待补充")}
"""


def write_note(
    output_dir: Path,
    candidate: CandidatePaper,
    draft: Mapping[str, str] | None = None,
    force: bool = False,
) -> tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / note_filename(candidate)
    if path.exists() and not force:
        return path, "skipped"
    action = "overwritten" if path.exists() else "created"
    path.write_text(render_note(candidate, draft), encoding="utf-8")
    return path, action


def has_all_required_sections(markdown: str) -> bool:
    return all(f"## {heading}" in markdown for heading in SECTION_HEADINGS)


def _slug(title: str, max_words: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title.lower())
    return "-".join(words[:max_words]) or "untitled"
