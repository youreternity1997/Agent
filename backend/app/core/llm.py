"""In-process vLLM AsyncLLMEngine for chat generation, plus a thin HTTP
client for the separate Ollama-served embedding model.

vLLM's AsyncLLMEngine runs its own background step loop and does continuous
batching: concurrent asyncio callers hitting generate() at the same time get
folded into the same GPU batch automatically, so multiple users chatting at
once doesn't serialize one request behind another the way a naive per-request
model load would.

Embeddings stay on Ollama (nomic-embed-text) - it's a separate small model
family, not something this generation engine serves.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import httpx

from app.core.config import get_settings

settings = get_settings()


class LLMError(RuntimeError):
    pass


def _describe_http_error(exc: httpx.HTTPError) -> str:
    """Pull Ollama's actual error body out of an HTTPStatusError.

    httpx's default str(exc) is generic boilerplate ("Client error '400 Bad
    Request' for url ...") and drops the response body, which is where
    Ollama puts the real reason.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text.strip()
        if body:
            return f"{exc} | 伺服器回應：{body}"
    return str(exc)


_engine = None
_tokenizer = None
_init_lock = asyncio.Lock()
_init_error: str | None = None


async def init_engine() -> None:
    """Load the vLLM engine + tokenizer once. Safe to call more than once -
    only the first call actually loads the model; a failed attempt is cached
    rather than retried, since re-attempting a multi-GB model load on every
    request would be far too slow to be useful (fix the underlying issue and
    restart the process instead).
    """
    global _engine, _tokenizer, _init_error
    async with _init_lock:
        if _engine is not None or _init_error is not None:
            return
        try:
            from transformers import AutoTokenizer
            from vllm import AsyncEngineArgs, AsyncLLMEngine

            engine_args = AsyncEngineArgs(
                model=settings.vllm_model,
                quantization=settings.vllm_quantization,
                max_model_len=settings.llm_num_ctx,
                gpu_memory_utilization=settings.vllm_gpu_memory_utilization,
                enforce_eager=settings.vllm_enforce_eager,
                attention_backend=settings.vllm_attention_backend,
                dtype="auto",
            )
            _engine = AsyncLLMEngine.from_engine_args(engine_args)
            _tokenizer = AutoTokenizer.from_pretrained(settings.vllm_model)
        except Exception as exc:  # noqa: BLE001
            _init_error = str(exc)
            raise LLMError(f"vLLM 引擎啟動失敗：{exc}") from exc


def is_ready() -> bool:
    return _engine is not None


def _require_engine() -> None:
    if _engine is None or _tokenizer is None:
        detail = f"（啟動時的錯誤：{_init_error}）" if _init_error else "，請稍候或檢查後端日誌"
        raise LLMError(f"本地 vLLM 引擎尚未就緒{detail}")


def _render_prompt(messages: list[dict]) -> str:
    return _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )


def _build_sampling_params(stop: list[str] | None):
    from vllm import SamplingParams

    return SamplingParams(
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stop=stop,
    )


async def chat_stream(messages: list[dict], stop: list[str] | None = None) -> AsyncGenerator[str, None]:
    """Run one generation on the local vLLM engine and yield the assistant
    text incrementally as it's produced."""
    _require_engine()
    prompt = _render_prompt(messages)
    sampling_params = _build_sampling_params(stop)
    request_id = str(uuid.uuid4())

    previous_text = ""
    got_any = False
    try:
        async for request_output in _engine.generate(prompt, sampling_params, request_id):
            current_text = request_output.outputs[0].text
            delta = current_text[len(previous_text) :]
            previous_text = current_text
            if delta:
                got_any = True
                yield delta
    except LLMError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"vLLM 推論時發生錯誤：{exc}") from exc

    if not got_any:
        raise LLMError("本地 LLM 回傳了空內容")


async def embed(text: str) -> list[float]:
    """Call the local Ollama embeddings endpoint."""
    url = f"{settings.ollama_base_url}/api/embeddings"
    payload = {"model": settings.ollama_embed_model, "prompt": text}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(
            f"無法連線到本地 Embedding 模型 ({settings.ollama_embed_model})：{_describe_http_error(exc)}"
        ) from exc

    embedding = data.get("embedding")
    if not embedding:
        raise LLMError("Embedding 模型回傳了空向量")
    return embedding
