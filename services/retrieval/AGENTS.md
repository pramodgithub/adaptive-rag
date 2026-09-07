# Retrieval Service Instructions

## Scope
- These instructions apply to retrieval, embedding, ranking, reranking, and retrieval evaluation code in this directory.

## Design Rules
- Keep retrieval execution separate from retrieval quality evaluation.
- Keep non-LLM evaluators deterministic and cheap to run.
- Keep LLM-based judges optional, isolated, and easy to disable in tests.
- Preserve existing result schemas and only add fields when downstream callers and tests are updated.
- Prefer explicit scores, reasons, thresholds, and strategy names over opaque booleans.

## Testing
- Update or add tests when changing retrieval scoring, filtering, fallback behavior, evaluator thresholds, or judge decisions.
- Use deterministic fixtures for evaluator tests.
- Avoid live embedding, vector database, or LLM calls in unit tests unless the test is explicitly marked as integration-level.
