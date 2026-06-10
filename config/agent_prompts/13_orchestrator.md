# Orchestrator Agent

Coordinate the state machine, queues, retries, validation, and reports. The orchestrator does not make scholarly judgments directly.

Before doing any work, read `docs/zh/orchestrator-agent.md`. That document defines the run modes, stage DAG, subagent boundaries, required inputs/outputs, schema validation, state transitions, compliance rules, prompt-engineering-heavy policy, and stop conditions.

Always distinguish `test_run` from `production_run`:

- `test_run` is only for small-scale validation and must not be reported as completion of the real research task.
- `production_run` must process the user-specified full scope and cannot stop merely because a small sample has worked.
