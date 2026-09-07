# RAG App Instructions

## Scope
- These instructions apply to the RAG application workflow, graph/state management, planning, and orchestration code.

## Workflow Rules
- Keep graph nodes focused on orchestration; place reusable retrieval, evaluation, ingestion, and generation logic in services.
- Preserve state model compatibility when adding fields. Update schemas and tests together.
- Make routing and retry decisions explicit in state so future debugging can explain why a path was taken.
- Do not hide retrieval failures behind generic generation failures; keep enough structured error information for diagnosis.

## Quality Gates
- When changing workflow behavior, verify both the direct unit tests and any tests that exercise state transitions.
- Prefer small graph changes with clear before/after behavior over broad rewrites.
