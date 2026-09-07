# Project Instructions

## Working Style
- Inspect the existing implementation before proposing or making changes.
- Prefer small, reviewable changes that preserve the current architecture.
- Explain changed files and behavior after each implementation step.
- Do not replace established frameworks, storage layers, orchestration patterns, or schemas unless the user explicitly asks or tests prove the current design is blocking progress.

## Architecture
- Treat this repository as an adaptive RAG / AI control platform.
- Keep retrieval, embedding, ingestion, evaluation, reranking, workflow orchestration, and API schemas separated by their existing module boundaries.
- Prefer typed schema objects from `core/schemas` and state models from `apps/rag/state` over ad hoc dictionaries.
- Keep deterministic logic separate from LLM-judged logic so behavior can be tested without external model calls.

## Data And Reliability
- Avoid hallucinated assumptions about database tables, vector indexes, environment variables, queue names, or service contracts. Verify them in code, migrations, configs, or tests first.
- Do not make network-dependent behavior required for unit tests.
- Keep retry, timeout, and fallback behavior explicit where external services are involved.

## Verification
- After code changes, run the smallest relevant test set first.
- For retrieval changes, start with retrieval and retrieval evaluator tests.
- Report any tests that could not be run and why.
