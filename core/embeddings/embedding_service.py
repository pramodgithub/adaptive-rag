from google import genai

from core.config.settings import settings


class EmbeddingService:

    def __init__(self):

        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

    def embed(self, text: str):

        result = self.client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text
        )

        return result.embeddings[0].values
