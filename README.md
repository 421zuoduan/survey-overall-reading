# Survey Overall Reading

Workflow helpers for moving from survey papers to traceable important-paper ranking, open-access PDF retrieval, deep-reading notes, and research-idea synthesis.

This repository is an early-stage implementation of a survey-to-paper reading system. The packaged CLI provides local, testable workflow tools: candidate paper scoring, reading policy filtering, Markdown note scaffolding, run state tracking, download-record reconciliation, agent-reviewed dedup plan application, one-paper-one-agent assignment generation, preflight checks, and QA checks. Production orchestration is agent-led: the Orchestrator Agent chooses stages, delegates semantic work to subagents, and invokes CLI tools for deterministic artifact transforms.

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
- Parse survey PDFs into machine-readable review JSON/Markdown artifacts.
- Extract bibliography entries and citation contexts for evidence-based ranking.
- Download only legal open-access PDFs and keep link-only records for unclear sources.
- Use a dedicated deduplication subagent for semantic same-paper decisions before applying merges.
- Prepare one-paper-one-agent deep-reading assignments to avoid context contamination, and keep the Orchestrator supervising batches until the queue is exhausted or explicitly blocked.
- Reconcile local PDFs against traceable source records before counting them as compliant downloads.

## Requirements

- Python 3.9 or newer
- `pypdf` for parse-level PDF verification

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

## Production Run Workflow

The intended full workflow is coordinated by an Orchestrator Agent following:

```text
docs/zh/orchestrator-agent.md
config/project.yaml
paper_reading_system_plan.md
config/agent_prompts/*.md
config/schemas/*.json
```

The stage DAG is:

```text
review_parse
  -> citation_extract
  -> importance_score
  -> metadata_normalize
  -> top_conference_supplement
  -> paper_discovery
  -> pdf_download
  -> deep_reading
  -> first_principles_critique
  -> note_write
  -> quality_audit
  -> idea_synthesis
```

The formal CLI does not yet expose every production stage. For current production runs, temporary scripts may live under ignored `workspace/` paths and must still write outputs to the project contract:

```text
workspace/extracted_reviews/
workspace/citation_graph/
workspace/candidate_papers/
workspace/top_conference_search/
workspace/download_queue/
papers/metadata/
papers/pdf/
notes/
reports/
```

Do not treat chat-only output as completion. Every stage should leave JSONL, JSON, Markdown, or report artifacts in the agreed directories.

The Orchestrator Agent, not a monolithic script, is the production entry point. CLI commands are deterministic tools with explicit inputs and outputs; they do not make semantic research decisions by themselves.

Current first-class CLI tools include:

```bash
python3 -m paper_reading_system reconcile-downloads
python3 -m paper_reading_system apply-dedup-plan
python3 -m paper_reading_system build-agentic-assignments
python3 -m paper_reading_system preflight-agentic-reading --archive-stale
```

Use temporary `workspace/` scripts only as short-lived scaffolding when no formal tool exists. Once a helper is useful beyond a single recovery run, either graduate it into `paper_reading_system/` or delete/archive it; it must not become a hidden production orchestrator.

## Compliance Rules

PDF downloads must be legal and traceable. Allowed sources include:

- arXiv
- OpenReview
- PMLR
- NeurIPS / AAAI / other official proceedings
- publisher open-access pages
- author homepages
- institutional repositories

Never bypass paywalls, login walls, institutional subscriptions, or access controls. If license or access status is unclear, save metadata/link-only and continue. A PDF counts as successfully downloaded only when `workspace/download_queue/download_records.jsonl` records a non-empty `source_url`, a known `source_type`, an open/free/preprint access status, and a local PDF that passes header, EOF, and page-parse verification.

If a local PDF exists but the source URL was lost, it must be marked for repair rather than silently counted as compliant. The reconciliation step may recover source fields from existing candidate or previous `download_record` data. An `identity.arxiv` value is only a discovery clue; by itself it is not sufficient provenance to verify a pre-existing local PDF.

## Agentic Deduplication

Deduplication is not only a string-matching problem. The project now prefers a dedicated deduplication subagent for semantic decisions when titles differ only slightly, when one record is an arXiv preprint and another is a conference/journal version, or when citation parsing has polluted DOI/arXiv fields.

Current artifacts:

```text
workspace/deep_reading_agentic/dedup_candidate_clusters.json
workspace/deep_reading_agentic/dedup_agent_plan.json
workspace/deep_reading_agentic/dedup_apply_report.json
reports/agentic_deduplication_report.md
```

The subagent should decide per cluster:

- `merge`: same paper or same work/version family
- `keep_separate`: related but distinct works
- `uncertain`: needs manual review

Code may generate suspicious duplicate clusters and mechanically apply the subagent plan, but code should not be the final authority for semantic same-paper decisions.

Current post-dedup production state:

```text
candidate rows: 403
download records: 403
verified downloaded PDFs: 214
parse-verified downloaded PDFs: 214
unverified / excluded local PDFs: 1
agentic reading assignments ready: 214
```

## One-Paper-One-Agent Deep Reading

For production-quality deep reading, use one isolated subagent per paper. This avoids context contamination across papers.

In a production run, the Orchestrator should keep launching and collecting reader batches until every assignment with a usable PDF has either a completed note, an explicit exclusion reason, or an explicit block recorded in the run summary. A handful of finished notes is only a progress checkpoint, not a completed run.

Current assignment artifacts:

```text
workspace/deep_reading_agentic/agentic_reading_manifest.jsonl
workspace/deep_reading_agentic/agentic_assignments.jsonl
workspace/deep_reading_agentic/assignments/{paper_id}.json
notes/deep_reading_agentic/
```

The canonical scheduling source is:

```text
workspace/deep_reading_agentic/agentic_assignments.jsonl
```

Do not schedule agents by globbing `workspace/deep_reading_agentic/assignments/*.json`; stale assignment files may be archived there for audit. The per-paper JSON files are convenience copies only. The JSONL manifest is the source of truth.

Each deep-reading subagent should:

- read exactly one assignment JSON
- read exactly one PDF and its metadata
- write exactly one note to `assignment.output_note`
- avoid reading other paper PDFs or other assignments
- avoid modifying legacy `notes/deep_reading/`

Each note should include:

- basic metadata
- problem and motivation
- core contributions
- method/mechanism
- experiments and evidence
- key figures/tables
- first-principles critique: root problem, assumptions, mechanism, falsifiable claims, transfer boundary
- relationship to the survey's LLM-agent-memory storyline
- possible research ideas
- low-confidence or manual-review items
- page or short source anchors for important judgments

Before launching reader subagents, run the agentic preflight:

```bash
python3 -m paper_reading_system preflight-agentic-reading --archive-stale
```

This writes:

```text
workspace/deep_reading_agentic/preflight_agentic_reading_report.json
reports/agentic_reading_preflight.md
```

The preflight checks assignment uniqueness, stale assignment files, PDF header/EOF, parseable page count, SHA-256 hash, copied canonical PDF lineage, and whether any downloaded item should be excluded from the reading queue.

Preflight reports two readiness levels:

- `assignment_ready`: safe to launch one-paper-one-agent readers from `agentic_assignments.jsonl`.
- `workspace_clean`: no stale metadata or PDF audit residue remains.

Stale metadata/PDF files do not by themselves block reader launch, but they must remain visible as audit residue and must never be used for scheduling.

## Agent / CLI Boundary

Production runs should follow this separation:

- The Orchestrator Agent decides run mode, schedules the DAG, launches subagents, handles semantic uncertainty, and records state.
- Deduplication subagents decide `merge`, `keep_separate`, or `uncertain` for suspicious duplicate clusters.
- One reader subagent reads exactly one paper and writes exactly one note.
- CLI tools verify and transform artifacts: score JSONL, reconcile download records, apply reviewed dedup plans, build assignment files, preflight PDFs, scaffold notes, and audit outputs.
- Package code must not silently replace agent judgment for semantic same-paper decisions or deep-reading interpretation.
- Dedup application is fail-closed: duplicate `paper_id` rows and invalid source/canonical references must be explicitly covered by the dedup subagent plan.
- Download records preserve `download_lineage` for merged aliases so PDF provenance remains auditable after deduplication.

The old `workspace/production_run.py`, `workspace/reconcile_run.py`, `workspace/apply_dedup_agent_plan.py`, and `workspace/preflight_agentic_reading.py` scripts were migration scaffolds. Their reusable deterministic behavior now lives in `paper_reading_system/`; the one-click production script is intentionally not a supported workflow.

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
papers/                  Downloaded PDFs and metadata, ignored by Git
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
- Download reconciliation and compliance reports as packaged CLI tools
- Agent-reviewed dedup plan application as a packaged CLI tool
- One-paper-one-agent assignment generation and preflight as packaged CLI tools
- Review PDF parsing in production runs
- Citation and context extraction in production runs
- Legal OA download records and compliance reports
- Agentic semantic deduplication workflow
- One-paper-one-agent assignment generation

Still needs formalization:

- First-class CLI commands for every production stage
- Full one-paper-one-agent deep reading execution, queue exhaustion, and QA
- Stronger figure/table extraction for deep-reading notes
- Automated idea novelty search against live literature sources
