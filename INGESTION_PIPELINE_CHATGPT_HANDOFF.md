# Ingestion Pipeline Review Handoff

Use this prompt with the repository's current source files. The original code paste repeated several classes and blocks; those repetitions are intentionally omitted here.

## Prompt

Please trace and diagnose the ingestion pipeline end to end. Do not assume Docling is the cause: determine whether any observed data loss or incorrect metadata originates in parsing, normalization, artifact serialization, structure inference, candidate-to-element mapping, splitting/persistence, embeddings, or graph construction. Verify every proposed fix against the source and add a focused regression test. Keep changes minimal and report the evidence and test command.

### Pipeline

1. `IngestionService.create_ingestion` saves the upload and commits document/version/job records, then queues `start_ingestion`.
2. The Celery chain runs `parse_document -> chunk_document -> embed_document -> build_graph`. Each stage passes a context dictionary forward.
3. `parse_document` chooses a parser by MIME type. PDF, DOCX and HTML use `DoclingParser`; plain text uses `TextParser`. The parser returns both a canonical document and chunk candidates. The task serializes both into a JSON artifact.
4. `chunk_document` restores the canonical document and candidates, infers structure on canonical elements, then creates chunks from candidate text. Candidate `source_refs` are mapped to canonical elements to populate section/identifier metadata. Chunks are split, reconciled by index in the database, and text changes clear existing embeddings.
5. Embedding and graph tasks complete the job and activate the document version.

### Concrete areas to verify

- `GenericStructureStrategy` assigns every heading a one-item section path and ignores the captured Docling nesting level. Check with a document containing nested headings; confirm whether expected ancestor paths are lost.
- Chunk creation depends on usable Docling candidates and matching `source_refs`; report candidate count, source-ref match rate, and chunks produced before changing parser behavior.
- Compare normalization of candidate text with canonical element text. Docling objects are normalized before chunking, while canonical conversion also applies a separate whitespace cleaner.
- `DoclingParser` loads `google/gemma-2-9b-it` with `AutoTokenizer.from_pretrained` during construction. Check whether model download/cache availability is implicated in worker or test failures.
- `tests/test_cached_ingestion_pipeline.py` asserts chunk count equals candidate count as well as a max length. That count assertion is invalid whenever a candidate is split; distinguish a test assumption from a production defect.

### Source files to inspect

- `services/ingestion/ingestion_service.py`
- `apps/worker/tasks/pipeline.py`
- `apps/worker/tasks/parse_task.py`, `chunk_task.py`, `embedding_task.py`, `graph_task.py`
- `services/ingestion/parsers/factory.py`, `docling_parser.py`, `text.py`, `chunk_candidate.py`
- `services/ingestion/domain/document.py`, `elements.py`, `serialization.py`
- `services/ingestion/normalization/text_normalizer.py`
- `services/ingestion/structure/structure_inference.py`, `generic_strategy.py`
- `services/ingestion/chunking/chunker.py`, `splitter.py`
- `tests/test_cached_ingestion_pipeline.py` and its fixtures

### Evidence to provide with the review

State the exact observed failure and expected result. Include file type/MIME type, a small sanitized input example, actual versus expected extracted text/heading/table/chunk metadata, parsed artifact counts (elements, candidates, matched refs), ingestion job error/log excerpt, and the focused test command/output. Do not include `.env`, credentials, or sensitive document contents. If evidence is missing, identify the smallest safe test or artifact inspection needed before proposing a fix.