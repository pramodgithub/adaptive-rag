from google import genai

from config.constants import EMBEDDING_DIMENSION
from core.config.settings import settings


class EmbeddingService:

    def __init__(self):

        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

    def embed(self, text: str) -> dict:

        result = self.client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text
        )
        values = result.embeddings[0].values

        if len(values) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, "
                f"got {len(values)} from model '{settings.EMBEDDING_MODEL}'"
            )

        return {
            "embedding": values,
            "model": settings.EMBEDDING_MODEL,
            "dimension": len(values),
        }
