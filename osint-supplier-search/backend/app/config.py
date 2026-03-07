from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = ""
    redis_url: str = "redis://localhost:6379"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    opencorporates_api_key: str = ""
    google_places_api_key: str = ""
    volza_email: str = ""
    volza_password: str = ""
    volza_session_cookie: str = ""  # Raw cookie string from browser after manual login
    scraper_api_key: str = ""  # Optional ScraperAPI key for CF-protected sites (scraperapi.com)

    environment: str = "development"
    log_level: str = "INFO"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ER thresholds
    er_auto_merge_threshold: float = 0.92
    er_ml_review_threshold: float = 0.75


settings = Settings()
