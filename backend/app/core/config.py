from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    secret_key: str
    fernet_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 60

    database_url: str
    redis_url: str
    qdrant_url: str
    qdrant_api_key: str = ""

    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect: str = ""
    github_webhook_secret: str = ""

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    mcp_github_server_cmd: str = "python -m app.mcp_servers.github_server"
    mcp_repo_search_server_cmd: str = "python -m app.mcp_servers.repo_search_server"

    # RAG
    repos_root: str = "/app/.repos"
    indexes_root: str = "/app/.indexes"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    chunk_max_lines: int = 120
    chunk_min_lines: int = 4
    max_file_bytes: int = 500_000
    
@lru_cache
def get_settings() -> Settings:
    return Settings()