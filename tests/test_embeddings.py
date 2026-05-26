from core.embeddings.embedding_service import (
    EmbeddingService
)

service = EmbeddingService()

result = service.embed(
    "What is Kubernetes?"
)

print(
    len(result)
)
