# Adaptive Agentic RAG Engine

A production-grade Retrieval-Augmented Generation system built with LangGraph. Supports multiple retrieval strategies, self-correction, confidence evaluation, and dynamic workflow orchestration.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [System Flow](#system-flow)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Roadmap](#roadmap)

---

## Overview

This system evolved from a traditional RAG pipeline into an adaptive reasoning engine. It dynamically selects retrieval strategies, evaluates confidence, rewrites queries when needed, and self-validates generated answers before returning a response.

**Core capabilities:**

- Multi-strategy retrieval: Vector, Web, Graph, and Tool-based
- Retrieval confidence scoring with automatic query rewriting
- Answer self-evaluation and hallucination reduction
- Full audit trail: token usage, latency per node, model metadata
- LLM routing with primary (Ollama) and fallback (Gemini) providers
- Non-linear workflow execution via LangGraph
- Observability via MLflow — node timing, eval scoring, LLM provider tracking


---

## Architecture

```
User Query
    │
    ▼
LangGraph Planner
    │
    ├──▶ Vector Strategy ──┐
    ├──▶ Web Strategy ─────┤
    ├──▶ Graph Strategy ───┼──▶ Retrieval Merge
    └──▶ Tool Strategy ────┘
                                │
                                ▼
                        Retrieval Evaluation
                                │
                    ┌───────────┴───────────┐
                    │                       │
             Low Confidence?          High Confidence
                    │                       │
                    ▼                       ▼
            Query Rewrite           Generate Response
                    │                       │
                    └───────────┬───────────┘
                                │
                                ▼
                        Answer Evaluation
                                │
                    ┌───────────┴───────────┐
                    │                       │
               Not Grounded             Grounded
                    │                       │
                    ▼                       ▼
                  Retry              Audit + Persist
                                           │
                                           ▼
                                    Return Response
```

---

## System Flow

Each request goes through the following lifecycle:

1. **Query received** — user submits a natural language query
2. **Strategy planning** — planner selects one or more retrieval strategies
3. **Retrieval** — selected strategies execute and results are merged
4. **Rerank** — results are scored and reranked by relevance
5. **Retrieval judge** — coverage, confidence, and relevance scored per source
6. **Query rewrite** *(if low confidence)* — query is reformulated and retrieval retried
7. **Generation** — LLM produces an answer grounded in retrieved context via ModelRouter (Ollama primary, Gemini fallback)
8. **Answer evaluation** — groundedness, confidence, and hallucination checks run
9. **Retry** *(if not grounded)* — generation retried with adjusted context
10. **Audit** — token usage, latency per node, source stats, and model metadata persisted
11. **Observability** — MLflow logs node durations, eval scores, token counts, provider tags, and execution ID per run
12. **Response returned** — final answer delivered to caller

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Workflow Engine | LangGraph |
| LLM Orchestration | LangChain |
| Vector Database | PostgreSQL + pgvector |
| Graph Database | Neo4j |
| Cache | Redis |
| Embeddings | Gemini Embedding 001 |
| LLM Primary | Ollama |
| LLM Fallback | Gemini |
| Async Workers | Worker Service |
| Containers | Docker |
| Observability | MLflow (node timing, eval scoring, LLM provider tracking) |

---

## Project Structure

```
adaptive-rag/
│
├── apps/
│   ├── api/                        # FastAPI application
│   └── worker/                     # Async task workers
│
├── graph/
│   ├── state.py                    # LangGraph state definitions
│   ├── nodes.py                    # Node implementations
│   ├── conditions.py               # Conditional routing logic
│   └── workflow.py                 # Graph assembly
│
├── services/
│   ├── retrieval/
│   │   ├── strategies/             # Vector, Web, Graph, Tool strategies
│   │   ├── retrieval_service.py    # Strategy execution
│   │   ├── retrieval_planner.py    # Strategy selection
│   │   └── reranker.py             # Result reranking
│   │
│   ├── evaluation/                 # Confidence + groundedness checks
│   ├── routing/                    # Dynamic workflow routing
│   ├── graph/                      # Neo4j graph service
│   └── audit/                      # Logging and tracing
│
├── database/                       # DB models and migrations
├── core/                           # Shared config and utilities
├── scripts/                        # Setup and tooling scripts
└── docker-compose.yml
```

---

## Observability

MLflow is integrated as the primary observability layer. Every query execution is tracked as a single MLflow run with the following telemetry:

### Execution Tracking

| Tag | Description |
|---|---|
| `execution_id` | Unique ID per request, correlates API logs to MLflow run |
| `provider` | LLM provider used — `ollama` or `gemini` |
| `model` | Specific model name used for generation |
| `fallback_used` | Whether the fallback provider was triggered |
| `fallback_reason` | Exception that caused primary provider failure |
| `node` | Node name that triggered the LLM call |

### Node Timing Metrics

| Metric | Description |
|---|---|
| `planner_duration` | Time to select retrieval strategies |
| `retrieve_duration` | Time to execute all retrieval strategies |
| `rerank_duration` | Time to rerank merged results |
| `judge_duration` | Time for retrieval judge evaluation |
| `generate_duration` | Time for LLM answer generation |
| `evaluate_duration` | Time for answer evaluation |

### Retrieval Metrics

| Metric | Description |
|---|---|
| `before_rerank` | Total chunks collected across all strategies |
| `after_rerank` | Chunks remaining after reranking |
| `retrieval_confidence` | Top chunk score from reranker |
| `judge_confidence` | LLM judge certainty score |
| `judge_coverage` | Context coverage score from judge |
| `judge_relevant` | Whether retrieved context was relevant |
| `source_{name}` | Chunk count per source (vector, web, graph, tool) |

### Evaluation Metrics

| Metric | Description |
|---|---|
| `confidence` | Answer confidence score |
| `grounded` | Whether answer passed groundedness check |
| `should_retry` | Whether retry was triggered |
| `retry_count` | Number of retries for this request |

### Token Metrics

| Metric | Description |
|---|---|
| `{node}_tokens` | Token usage per node (planner, answer, evaluator etc.) |

### Accessing the MLflow UI

```bash
http://localhost:5001
```

---

## API Reference

### Query Endpoint

**POST** `/query`

**Request**
```json
{
  "query": "What are Pods in Kubernetes?"
}
```

**Response**
```json
{
  "answer": "Pods are the smallest deployable unit in Kubernetes.",
  "execution_id": "3f7a1c2e-...",
  "strategies": ["vector"],
  "retrieval_stats": {
    "before_rerank": 12,
    "after_rerank": 5,
    "sources": {
      "vector": { "count": 3, "avg_score": 0.85, "max_score": 0.89, "min_score": 0.79 },
      "web":    { "count": 2, "avg_score": 0.76, "max_score": 0.81, "min_score": 0.71 }
    }
  },
  "evaluation": {
    "grounded": true,
    "confidence": 0.88,
    "should_retry": false
  },
  "node_metrics": {
    "planner":  0.342,
    "retrieve": 0.451,
    "rerank":   0.123,
    "judge":    0.834,
    "generate": 1.243,
    "evaluate": 0.756
  }
}
```

**Response fields:**

| Field | Description |
|---|---|
| `answer` | Generated response grounded in retrieved context |
| `execution_id` | Unique run ID — use to find this request in MLflow |
| `strategies` | Retrieval strategies used for this query |
| `retrieval_stats` | Chunk counts and scores per source before and after rerank |
| `evaluation.grounded` | Whether the answer passed groundedness checks |
| `evaluation.confidence` | Answer confidence score 0–1 |
| `node_metrics` | Latency in seconds per node |

---

## Why LangGraph

The RAG workflow is non-linear. Depending on retrieval confidence and answer quality, the system may loop, branch, or retry. LangGraph handles this naturally by providing:

- Stateful execution across nodes
- Conditional branching and routing
- Built-in retry and loop support
- Clean separation of orchestration from logic

A linear pipeline cannot express this workflow cleanly. LangGraph makes the control flow explicit and inspectable.

---

## Roadmap

- [ ] Cross-encoder reranking
- [ ] MCP tool execution
- [ ] Knowledge graph auto-generation
- [ ] Persistent memory layer
- [ ] Human-in-the-loop approval gates
- [ ] LangSmith tracing integration
- [ ] OpenTelemetry support
- [ ] Multi-agent workflow expansion

---

## Status

**Current phase:** Production-grade MVP