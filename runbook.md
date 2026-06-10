# Paper Reading System Runbook

## Quick Start

1. Put review PDFs in `inputs/reviews/pdf/` or metadata in `inputs/reviews/metadata/`.
2. Create candidate JSONL at `workspace/candidate_papers/candidates.jsonl`.
The source-tree command is `python3 -m paper_reading_system`. If the package is installed, the equivalent console command is `paper-reading`.

3. Score candidates:

```bash
python3 -m paper_reading_system score-candidates
```

4. Create Markdown note scaffolds:

```bash
python3 -m paper_reading_system scaffold-notes
```

Existing note files are preserved by default. Use `--force` only when you intentionally want to regenerate and overwrite note scaffolds.

`notes/index.md` is an auto-generated index and may be refreshed by `scaffold-notes`; keep manual reading content inside `notes/deep_reading/*.md`.

5. Audit generated notes:

```bash
python3 -m paper_reading_system audit
```

The current implementation is offline-first. Network discovery and PDF download agents are represented by config, schemas, and prompts, but do not automatically access the network yet.

## Reading Policy

Papers whose main contribution is mostly prompt engineering are kept as metadata/evidence but skipped for deep reading by default. Mark such candidates with `tags: ["prompt_engineering_heavy"]` or `raw_scores.prompt_engineering_dependency >= 0.70`.
