# Test Instructions

## Test Style
- Prefer focused tests that describe behavior from the caller's perspective.
- Keep unit tests deterministic and independent of network, live databases, background workers, or external LLM calls.
- Use small fixtures that make scoring, ranking, and fallback behavior obvious.
- When a production schema changes, update tests to assert the new contract explicitly.

## Retrieval Tests
- Cover normal retrieval, empty results, low-confidence results, fallback paths, and evaluator boundary conditions.
- For evaluator changes, test both the numeric score and the explanation/reason fields when available.
- Add regression tests for bugs before or alongside fixes.
