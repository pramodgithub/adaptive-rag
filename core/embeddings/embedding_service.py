from core.config.settings import settings
from config.constants import EMBEDDING_DIMENSION
from google import genai
from google.genai import types
import re
import time
import logging
from google.genai import errors

logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self):
        raw = getattr(settings, "GEMINI_API_KEYS",
                      "") or settings.GEMINI_API_KEY
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        self.clients = [genai.Client(api_key=k) for k in keys]
        self._key_index = 0
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

        max_retries = settings.EMBED_MAX_429_RETRIES
        config = types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSION,
            task_type="RETRIEVAL_DOCUMENT"
        )

        for attempt in range(max_retries + 1):
            client = self.clients[self._key_index % len(self.clients)]
            try:
                result = client.models.embed_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                break
            except errors.ClientError as e:
                if e.code != 429 or attempt == max_retries:
                    raise
                match = re.search(r"retry in ([\d.]+)s", str(e))
                wait = float(match.group(1)) + 2 if match else 60
                logger.warning(
                    "429 hit, waiting %.0fs (attempt %s)", wait, attempt + 1)
                self._key_index += 1      # try the next key next time
                time.sleep(wait)

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
