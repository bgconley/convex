from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex"
    redis_url: str = "redis://localhost:6380/0"
    embedder_url: str = "http://localhost:8082"
    data_dir: str = "/data"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dim: int = 1024

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    cors_origins: list[str] = ["*"]
