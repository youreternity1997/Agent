# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# libc6-dev is required alongside gcc: the python:3.11-slim base has gcc's
# runtime libs but not the static startup objects (crti.o etc.), so without
# it gcc can compile but not link - which silently breaks Triton's JIT
# kernel compilation (vLLM's TRITON_ATTN backend needs to compile CUDA
# kernels at container startup) with "cannot find crti.o".
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev libpq-dev curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# vLLM pulls several GB of CUDA/torch wheels - cache them in a BuildKit mount
# (persists across builds even when the image layer cache is invalidated or
# a build gets interrupted) instead of re-downloading everything every time.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Workaround: flashinfer-python 0.6.16.post3 (exact version pinned by
# vllm==0.27.1) has an eagerly-evaluated `array.array[int]` return-type
# annotation that raises "TypeError: type 'array.array' is not subscriptable"
# on import under Python 3.11 - array.array doesn't support subscripting.
# Deferring annotation evaluation in just this file sidesteps it without
# touching vllm's pinned version. Upstream fix: flashinfer-ai/flashinfer#4354.
RUN sed -i "1i from __future__ import annotations" \
    /usr/local/lib/python3.11/site-packages/flashinfer/comm/fd_exchange.py

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
