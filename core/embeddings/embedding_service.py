from google import genai
from google.genai import types

from config.constants import EMBEDDING_DIMENSION
from core.config.settings import settings


class EmbeddingService:

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )
        self.model_name = settings.EMBEDDING_MODEL

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"Text at index {index} must be a string"
                )

            if not text.strip():
                raise ValueError(
                    f"Text at index {index} is empty"
                )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=text)]
            )
            for text in texts
        ]

        result = self.client.models.embed_content(
            model=self.model_name,
            contents=contents,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSION,
                task_type="RETRIEVAL_DOCUMENT"
            )
        )

        embeddings = [
            embedding.values
            for embedding in result.embeddings
        ]

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: expected {len(texts)}, "
                f"got {len(embeddings)}"
            )

        for index, embedding in enumerate(embeddings):
            if embedding is None:
                raise ValueError(
                    f"Embedding at index {index} is None"
                )

            if len(embedding) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Embedding dimension mismatch at index {index}: "
                    f"expected {EMBEDDING_DIMENSION}, "
                    f"got {len(embedding)}"
                )

        return embeddings
