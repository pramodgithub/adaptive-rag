from core.embeddings.embedding_service import (
    EmbeddingService
)


service = EmbeddingService()
text = "This is a test document for embedding generation."

result = service.embed(text)
vector = result["embedding"]   # ← adjust key name to match actual return

print("Type:", type(vector))
print("Length:", len(vector))
print("First values:", vector[:5])
print("Model:", result.get("model"))
