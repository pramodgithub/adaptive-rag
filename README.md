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
- Full audit trail: token usage, latency, model metadata
- Non-linear workflow execution via LangGraph

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
3. **Retrieval** — selected strategies execute in parallel
4. **Merge** — results are combined and deduplicated
5. **Confidence check** — retrieval quality is scored
6. **Query rewrite** *(if low confidence)* — query is reformulated and retrieval retried
7. **Generation** — LLM produces an answer grounded in retrieved context
8. **Answer evaluation** — groundedness and hallucination checks run
9. **Retry** *(if not grounded)* — generation retried with adjusted context
10. **Audit** — token usage, latency, and metadata persisted
11. **Response returned** — final answer delivered to caller

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
| LLM Models | Ollama (primary) + Gemini (fallback) |
| Async Workers | Worker Service |
| Containers | Docker |
| Observability | Audit Logs |

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
  "strategies": ["vector"],
  "retrieval": {
    "confidence": 0.71
  },
  "evaluation": {
    "grounded": true
  }
}
```

**Response fields:**

| Field | Description |
|---|---|
| `answer` | Generated response grounded in retrieved context |
| `strategies` | Retrieval strategies used for this query |
| `retrieval.confidence` | Score from 0–1 indicating retrieval quality |
| `evaluation.grounded` | Whether the answer passed groundedness checks |

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