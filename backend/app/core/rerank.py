"""Local cross-encoder reranker for narrowing RAG candidates.

pgvector's cosine-distance search is a bi-encoder retrieval step: fast, but
it scores query and chunk independently so it misses fine-grained relevance.
A cross-encoder reranker reads (query, chunk) pairs together and produces a
much better relevance ranking - it's just too slow to run over the whole
knowledge base, so it only re-scores the top candidates the vector search
already narrowed down.

Runs on CPU by default (see config.py's rerank_device note: the GPU is
already ~fully committed to vLLM's KV cache on this hardware). Loaded lazily
and cached, mirroring app.core.llm's engine init pattern.
"""

import asyncio

from app.core.config import get_settings

settings = get_settings()


class RerankError(RuntimeError):
    pass


_tokenizer = None
_model = None
_init_lock = asyncio.Lock()
_init_error: str | None = None


async def _ensure_loaded() -> None:
    global _tokenizer, _model, _init_error
    if _model is not None:
        return
    async with _init_lock:
        if _model is not None or _init_error is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            def _load():
                tokenizer = AutoTokenizer.from_pretrained(settings.rerank_model)
                model = AutoModelForSequenceClassification.from_pretrained(settings.rerank_model)
                model.to(settings.rerank_device)
                model.eval()
                return tokenizer, model

            _tokenizer, _model = await asyncio.to_thread(_load)
        except Exception as exc:  # noqa: BLE001
            _init_error = str(exc)
            raise RerankError(f"Rerank 模型載入失敗：{exc}") from exc


def _score_pairs(query: str, documents: list[str]) -> list[float]:
    import torch

    pairs = [[query, doc] for doc in documents]
    with torch.no_grad():
        inputs = _tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(settings.rerank_device)
        logits = _model(**inputs, return_dict=True).logits.view(-1).float()
        scores = torch.sigmoid(logits)
    return scores.tolist()


async def rerank(query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
    """Score each document against the query and return the top_k
    (original_index, score) pairs, sorted by descending relevance."""
    if not documents:
        return []

    await _ensure_loaded()
    scores = await asyncio.to_thread(_score_pairs, query, documents)
    ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]
