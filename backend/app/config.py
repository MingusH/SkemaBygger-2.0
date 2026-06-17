from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/skemabygger"
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # CP-SAT solver tuning. Defaults are safe for a small/fractional-CPU host (e.g.
    # Render free tier): 1 search worker avoids oversubscribing a 0.1-CPU instance.
    # Bump SOLVER_NUM_WORKERS locally (e.g. to your core count) for faster dev solves.
    solver_num_workers: int = 1
    solver_max_time_seconds: float = 60.0

    # Public base URL of this service (scheme + host, no trailing slash). Used to build
    # OAuth issuer / redirect URLs. Set PUBLIC_BASE_URL on Render to the service URL.
    public_base_url: str = "http://localhost:8000"

    # Comma-separated allowed CORS origins (the web frontend). Set CORS_ORIGINS on Render
    # to the static site URL, e.g. "https://skemabygger-web.onrender.com".
    cors_origins: str = "http://localhost:5173,http://frontend:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy needs the 'postgresql://' scheme; managed hosts (Render) often
        hand out 'postgres://'. Normalize it."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
