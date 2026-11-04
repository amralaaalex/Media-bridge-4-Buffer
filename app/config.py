from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BUFFER_AUTH_URL = "https://auth.buffer.com/auth"
BUFFER_TOKEN_URL = "https://auth.buffer.com/token"
BUFFER_API_URL = "https://api.buffer.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_base_url: str = "https://localhost:8000"
    session_secret: str
    token_encryption_key: str
    media_ttl_days: int = 60

    buffer_client_id: str
    buffer_client_secret: str
    buffer_redirect_uri: str = "https://localhost:8000/callback"
    buffer_scopes: str = "posts:read posts:write account:read offline_access"

    database_url: str = "sqlite:///./dev.db"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
