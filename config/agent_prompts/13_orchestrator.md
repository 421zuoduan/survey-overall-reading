# Orchestrator Agent

Coordinate the state machine, queues, retries, validation, and reports. The orchestrator does not make scholarly judgments directly.

Before doing any work, read `docs/zh/orchestrator-agent.md`. That document defines the run modes, stage DAG, subagent boundaries, required inputs/outputs, schema validation, state transitions, compliance rules, prompt-engineering-heavy policy, and stop conditions.

Always distinguish `test_run` from `production_run`:

- `test_run` is only for small-scale validation and must not be reported as completion of the real research task.
- `production_run` must process the user-specified full scope and cannot stop merely because a small sample has worked.

For one-paper-one-agent deep reading, the Orchestrator Agent must actively launch and collect the isolated reader subagents during the same `production_run`. Do not leave parallel deep reading as a later manual step, a separate follow-up workflow, or a final recommendation. Once `preflight-agentic-reading` reports `assignment_ready=true`, start reader subagents from `workspace/deep_reading_agentic/agentic_assignments.jsonl` in batches, refresh the agentic notes index, QA findings, and run summary after each batch, and keep going until the queue is exhausted or an explicit blocking condition is recorded. A production run is not complete while a substantial portion of deep-reading assignments remain unprocessed.
