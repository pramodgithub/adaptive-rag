# Production-grade document processing

                    Document
                       │
                       ▼
              ┌─────────────────┐
              │ Document Parser │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Text         Tables       Metadata
          │            │            │
          └────────────┼────────────┘
                       ▼
               Structural Model
                       │
                       ▼
              Semantic Chunker
                       │
                       ▼
               Chunk Enrichment
                       │
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
       Embedding    Evidence       Entities
          │         metadata          │
          ▼            │              ▼
      pgvector        │            Neo4j
                       │
                       ▼
                  PostgreSQL


## Docling → Knowledge Graph Architecture

                Docling
                    │
                    ▼
             Canonical Document
                    │
                    ▼
              Semantic Chunks
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
       pgvector             Entity
       retrieval           extraction
                              │
                              ▼
                             Neo4j

### PostgreSQL
    Keep as the system of record for:
    - tenants
    - documents
    - versions
    - chunks
    - ingestion state
    - compliance assessments
    - policies
    - audit records
    - evaluation results
    - model metadata
### Neo4j
    Use for:
    - regulations
    - requirements
    - controls
    - entities
    - organizations
    - systems
    - frameworks
    - relationships
    - dependencies
    - mappings
    - exceptions
    - evidence relationships

This gives us:
- Postgres = transactional truth

- Neo4j = relationship intelligence

- pgvector = semantic retrieval


### 
                  Query
                    │
                 Planner
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
      Vector       Graph        Web/Tools
        │           │            │
        └───────────┼────────────┘
                    ▼
              Result Fusion
                    │
                  Rerank
                    │
               Evaluation

-- Example
Eventually a question like:
"What controls apply to an Indian fintech handling EU customer data?"

might require:
Vector:
     find relevant controls

Graph:
     Fintech
       ↓
     India
       ↓
     GDPR
       ↓
     personal data
       ↓
     applicable requirements
       ↓
     mapped controls

Metadata:
     effective date
     jurisdiction
     applicability

Evidence:
     organization documents