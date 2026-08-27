"""Thin async wrapper around a local Ollama instance.

Deliberately uses the plain /api/chat completion endpoint rather than
Ollama's tool-calling support: small ~4B local models are unreliable at
native function-calling, so the ReAct loop instead asks the model to emit
plain-text `Thought / Action / Action Input` blocks that we parse ourselves.
"""

import json
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
    Ollama/llama.cpp put the real reason (e.g. context-size overflow).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text.strip()
        if body:
            return f"{exc} | 伺服器回應：{body}"
    return str(exc)


def _build_payload(messages: list[dict], stream: bool, stop: list[str] | None) -> dict:
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": stream,
        "think": False,
        "options": {
            "temperature": settings.llm_temperature,
            "num_ctx": settings.llm_num_ctx,
        },
    }
    if stop:
        payload["options"]["stop"] = stop
    return payload


async def chat(messages: list[dict], stop: list[str] | None = None) -> str:
    """Call the local Ollama chat endpoint and return the assistant text."""
    payload = _build_payload(messages, stream=False, stop=stop)

    url = f"{settings.ollama_base_url}/api/chat"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(
            f"無法連線到本地 LLM ({settings.ollama_base_url})，"
            f"請確認 Ollama 已啟動且已 pull 模型 '{settings.ollama_model}'：{_describe_http_error(exc)}"
        ) from exc

    message = data.get("message", {})
    content = message.get("content", "")
    if not content:
        raise LLMError("本地 LLM 回傳了空內容")
    return content


async def chat_stream(messages: list[dict], stop: list[str] | None = None) -> AsyncGenerator[str, None]:
    """Call the local Ollama chat endpoint and yield the assistant text incrementally."""
    payload = _build_payload(messages, stream=True, stop=stop)
    url = f"{settings.ollama_base_url}/api/chat"

    got_any = False
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code >= 400:
                    # Streaming responses aren't auto-read; must read the body
                    # ourselves before it's available on the raised exception.
                    error_body = (await resp.aread()).decode(errors="replace").strip()
                    detail = f"HTTP {resp.status_code}"
                    if error_body:
                        detail += f" | 伺服器回應：{error_body}"
                    raise LLMError(
                        f"無法連線到本地 LLM ({settings.ollama_base_url})，"
                        f"請確認 Ollama 已啟動且已 pull 模型 '{settings.ollama_model}'：{detail}"
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        got_any = True
                        yield chunk
                    if data.get("done"):
                        break
    except httpx.HTTPError as exc:
        raise LLMError(
            f"無法連線到本地 LLM ({settings.ollama_base_url})，"
            f"請確認 Ollama 已啟動且已 pull 模型 '{settings.ollama_model}'：{_describe_http_error(exc)}"
        ) from exc

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
