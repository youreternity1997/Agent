from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (local, in-process vLLM AsyncLLMEngine)
    vllm_model: str = "Qwen/Qwen3-8B-AWQ"
    vllm_quantization: str = "awq"
    vllm_gpu_memory_utilization: float = 0.85
    # Skips vLLM's torch.compile optimization path. That path pulls in
    # flashinfer's multi-GPU AllReduce fusion pass, which is both irrelevant
    # for our single-GPU setup and currently broken on Python 3.11
    # (TypeError: type 'array.array' is not subscriptable).
    vllm_enforce_eager: bool = True
    # vLLM has no VLLM_ATTENTION_BACKEND env var as of 0.27.1 (removed in
    # favor of the --attention-backend CLI flag / AsyncEngineArgs kwarg) -
    # setting it as a raw environment variable is a silent no-op, so it has
    # to be threaded through explicitly in llm.py's AsyncEngineArgs call.
    vllm_attention_backend: str | None = None
    llm_temperature: float = 0.2
    llm_num_ctx: int = 8192
    llm_max_tokens: int = 2048

    # Embedding (local, via Ollama - separate small model, not served by vLLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"

    # Database
    database_url: str = "postgresql+asyncpg://gigabyte:gigabyte@localhost:5432/gigabyte_agent"
    database_url_sync: str = "postgresql://gigabyte:gigabyte@localhost:5432/gigabyte_agent"

    # Agent
    max_react_steps: int = 6
    llm_context_window_messages: int = 20
    max_stored_messages_per_conversation: int = 500

    # Voice input (local Whisper transcription)
    whisper_model_size: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Hardware status WebSocket
    system_ws_interval_seconds: float = 2.0

    # File upload -> LlamaIndex ingestion
    upload_chunk_size: int = 500
    upload_chunk_overlap: int = 150
    upload_max_file_size_mb: int = 100

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
