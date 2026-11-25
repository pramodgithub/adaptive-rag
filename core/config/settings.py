from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DATABASE_URL: str

    GEMINI_API_KEY: str

    EMBEDDING_MODEL: str

    TAVILY_API_KEY: str

    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str

    EMBED_BATCH_SIZE: int
    EMBED_BATCH_DELAY_SECONDS: int
    EMBED_MAX_429_RETRIES: int

    class Config:
        env_file = ".env"


settings = Settings()
