### Governance
                    GOVERNANCE PLANE
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Policy       Model       Prompt       Data         │
│  Registry     Registry    Registry     Registry     │
│                                                     │
│  Evaluation   Approval    Versioning   Change       │
│  Policies     Workflow                 Management   │
│                                                     │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
                   RAG Runtime

## Model governance
 Track:
   - provider
   - model
   - model version
   - embedding model
   - embedding version
   - temperature
   - token limits
   - system prompt version

## Prompt governance
   - prompt_id
   - version
   - purpose
   - owner
   - created_at
   - approved_at
   - status

## Retrieval policy governance
Same thing.

## Guardrail governance
Same thing.

## Knowledge governance
Every regulation/control should have:
   - source
   - authority
   - jurisdiction
   - effective date
   - expiration date
   - verification
   - confidence
   - version

## Guardrails
# Input guardrails
    Detect:
    - prompt injection
    - malicious instructions
    - excessive query scope
    - unauthorized tenant access
    - sensitive data requests

# Retrieval guardrails
    Ensure:
    - tenant isolation
    - jurisdiction applicability
    - effective date
    - authority
    - document status
    - source provenance
# Generation guardrails
    Ensure:
    - answer grounded in evidence
    - citations
    - no unsupported claims
    - no invented controls
    - no invented regulatory requirements
# Output guardrails
    For example:
    Claim
    ↓
    Evidence?
    ├── YES → allow
    └── NO  → reject / qualify

## Observability
# request should have a trace like    
    trace_id
    │
    ├── planner
    │     ├── strategy selected
    │     └── latency
    │
    ├── retrieval.vector
    │     ├── query
    │     ├── embedding model
    │     ├── top_k
    │     ├── scores
    │     └── latency
    │
    ├── retrieval.graph
    │
    ├── reranker
    │
    ├── evaluator
    │
    ├── judge
    │
    ├── rewrite
    │
    ├── generation
    │     ├── model
    │     ├── tokens
    │     ├── latency
    │     └── cost
    │
    ├── guardrails
    │
    └── audit

## use OpenTelemetry as the instrumentation standard rather than making MLflow the only observability layer. 
# MLflow
    Keep it for:
    - experiments
    - evaluation
    - model/prompt experiments
    - benchmark runs

# OpenTelemetry
    Use for:
    - runtime traces
    - metrics
    - logs
    - distributed tracing
    - LLM/tool spans

## Drift monitoring
# 1. Data drift
    Example:
    Document vocabulary changes
    Chunk length changes
    New regulations appear
    Old regulations disappear
# 2. Embedding drift
    If you change:
    Gemini embedding model A
            ↓
    embedding model B
    your vector space changes.
    That can silently destroy retrieval quality.
    Therefore:
    embedding_model
    embedding_version
    dimension
    must be tracked.
# 3. Retrieval drift
    Monitor:
    top-k score distribution
    MRR
    Recall@K
    NDCG
    empty retrieval rate
    retry rate
    judge invocation rate
    insufficient evidence rate
    Example:
    Last month:
    top1 score = 0.78

    This month:
    top1 score = 0.61
    That should trigger investigation.
# 4. Answer drift
    Monitor:
   - groundedness
   - citation correctness
   - completeness
   - hallucination rate
   - human feedback
   - answer confidence

## Compliance Intelligence
        Regulation
            ↓
        Requirement
            ↓
        Control
            ↓
        Organization
            ↓
        Evidence
            ↓
        Assessment
            ↓
        Gap
            ↓
        Risk
            ↓
        Remediation
            ↓
        Verification   

# Neo4j becomes very useful here.

        GDPR Article X
        │
        ├── requires → Access Control
        │
        └── mapped_to
                ↓
            Control CC6
                │
                ├── implemented_by
                ↓
            Organization System
                │
                └── evidenced_by
                        ↓
                    SOC2 Evidence

Now the platform can answer:
- Which requirements are not currently evidenced?

rather than just:
- What does this document say?

## Multi-tenancy
multiple organizations, sectors, countries, regulations.
Every major entity should ultimately carry something like:
- tenant_id
- organization_id
And retrieval must enforce:
    tenant
    +
    organization
    +
    document status
    +
    version
    +
    jurisdiction
    +
    sector
    +
    effective date