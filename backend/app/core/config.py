from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (local, via Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b-instruct"
    ollama_embed_model: str = "nomic-embed-text"
    llm_temperature: float = 0.2

    # Database
    database_url: str = "postgresql+asyncpg://gigabyte:gigabyte@localhost:5432/gigabyte_agent"
    database_url_sync: str = "postgresql://gigabyte:gigabyte@localhost:5432/gigabyte_agent"

    # Agent
    max_react_steps: int = 6

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Paths
    backend_root: Path = Path(__file__).resolve().parents[2]
    skills_dir: Path = Path(__file__).resolve().parents[1] / "skills"
    mcp_server_script: Path = Path(__file__).resolve().parents[1] / "mcp_server" / "server.py"


@lru_cache
def get_settings() -> Settings:
    return Settings()
