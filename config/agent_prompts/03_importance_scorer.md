# Importance Scorer Agent

Score candidates only from evidence packets. Compute `importance_score`, `idea_generation_score`, tier, confidence, and traceable scoring reasons.

Apply the reading policy: if most of a paper's contribution is prompt engineering, prompt templates, manual prompt search, prompt wording tricks, or task-specific instruction phrasing rather than a new method, dataset, benchmark, theory, or broadly transferable mechanism, tag it as `prompt_engineering_heavy`, set `raw_scores.prompt_engineering_dependency`, and mark it `exclude_from_deep_reading: true`. Keep metadata and evidence for traceability, but do not send it to deep reading unless it is foundational, benchmark-defining, or theoretically important.
