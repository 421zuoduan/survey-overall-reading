# Survey Overall Reading

Offline-first workflow helpers for moving from survey papers to traceable important-paper ranking and deep-reading note scaffolds.

This repository is an early-stage implementation of a survey-to-paper reading system. It currently focuses on the local, testable workflow core: candidate paper scoring, reading policy filtering, Markdown note scaffolding, run state tracking, and QA checks. Network discovery and PDF downloading are represented by configuration, schemas, and agent prompts, but are not automated yet.

## 中文文档

- [中文使用文档](docs/zh/usage.md)

## Features

- Score candidate papers with separate `importance_score`, `idea_generation_score`, and `selection_score`.
- Generate stable `paper_id` values and one Markdown deep-reading note per selected paper.
- Preserve existing notes by default; use `--force` only when intentionally regenerating.
- Skip deep reading for papers whose main contribution is mostly prompt engineering, while keeping metadata and evidence.
- Record workflow status in a local SQLite state database.
- Produce ranked paper reports, note indexes, and QA findings.
- Keep generated outputs, PDFs, caches, and local state out of Git via `.gitignore`.

## Requirements

- Python 3.9 or newer
- No runtime third-party Python dependency is required for the current offline core.

## Quick Start

Clone or enter the repository, then run commands from the project root.

```bash
python3 -m paper_reading_system --help
python3 -m paper_reading_system init
```

Put review PDFs here:

```text
inputs/reviews/pdf/
```

Create candidate paper JSONL here:

```text
workspace/candidate_papers/candidates.jsonl
```

Then run:

```bash
python3 -m paper_reading_system score-candidates
python3 -m paper_reading_system scaffold-notes
python3 -m paper_reading_system audit
```

If the package is installed, the console entry point is also available:

```bash
paper-reading --help
```

## Candidate JSONL Example

Each line in `workspace/candidate_papers/candidates.jsonl` is one candidate paper:

```json
{"identity":{"title":"Attention Is All You Need","authors":["Ashish Vaswani"],"year":2017,"venue":"NeurIPS","arxiv":"1706.03762"},"candidate_source":["review_citation"],"raw_scores":{"cross_review_recurrence":0.9,"structural_centrality":0.95,"citation_context_strength":1.0,"foundational_or_benchmark_role":1.0},"idea_scores":{"evolution_chain_position":1.0,"methodological_transferability":1.0}}
```

To mark a paper as mostly prompt-engineering-based and skip deep reading:

```json
{"identity":{"title":"Prompt Tricks for Everything","authors":["A. Author"],"year":2024},"tags":["prompt_engineering_heavy"],"raw_scores":{"citation_context_strength":0.8,"prompt_engineering_dependency":0.9}}
```

## Repository Layout

```text
config/                  Project config, schemas, and agent prompts
docs/                    User-facing documentation
inputs/reviews/pdf/      Local survey PDFs, ignored by Git
paper_reading_system/    Python package and CLI implementation
tests/                   Unit tests
workspace/               Runtime state, caches, and generated JSONL, ignored by Git
notes/                   Generated reading notes, ignored by Git
reports/                 Generated reports, ignored by Git
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The current suite covers candidate validation, scoring, note scaffolding, duplicate detection, state regression protection, prompt-engineering filtering, and CLI workflow behavior.

## Project Status

Implemented:

- Offline CLI skeleton
- Candidate scoring
- Candidate input validation
- Stable note scaffolding
- Prompt-engineering-heavy reading policy
- Local state tracking
- QA report generation
- Unit tests

Not implemented yet:

- Automatic PDF parsing
- Citation extraction from review PDFs
- Network metadata discovery
- Open-access PDF downloading
- Full deep-reading content generation
- Idea novelty search

