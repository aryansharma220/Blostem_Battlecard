from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    sqlite_path: str = "./battlecard.db"
    cache_ttl_seconds: int = 3600
    max_pipeline_seconds: int = 60

    # Deduplication and postprocessing tuning
    dedupe_similarity_threshold: float = 0.82
    dedupe_limit: int = 60
    post_max_bullets: int = 5
    post_max_words_per_bullet: int = 500
    # Minimum number of ranked sources required for confident generation
    min_sources: int = 5

    groq_api_key: str = ""
    groq_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
