from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex"
    redis_url: str = "redis://localhost:6380/0"
    data_dir: str = "/data"

    # ML services — use existing GPU server infrastructure
    # Gateway at :8080 provides OpenAI-compatible /v1/embeddings
    embedder_url: str = "http://localhost:8080"
    reranker_url: str = "http://localhost:9006"
    ner_url: str = "http://localhost:9002"
    embedding_model: str = "qwen3-embedder"
    embedding_dim: int = 1024

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    cors_origins: list[str] = ["*"]
