"""WebSocket that periodically pushes host hardware status (CPU/RAM/GPU) and
the local LLM/embedding model status, so the frontend sidebar can show it live.

This is a separate channel from the chat SSE stream (/api/chat) - it never
touches the ReAct loop.
"""

import asyncio
from contextlib import suppress

import httpx
import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import llm
from app.core.config import get_settings

router = APIRouter(tags=["system"])
settings = get_settings()

_NVIDIA_SMI_FIELDS = (
    "name,utilization.gpu,utilization.memory,memory.total,memory.used,"
    "temperature.gpu,power.draw,fan.speed"
)


def _cpu_status() -> dict:
    freq = psutil.cpu_freq()
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else None
    # A single percpu call avoids the skew from calling cpu_percent() twice back-to-back.
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    overall = round(sum(per_core) / len(per_core), 1) if per_core else 0.0
    return {
        "percent": overall,
        "per_core": per_core,
        "cores_logical": psutil.cpu_count(logical=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "freq_current_mhz": round(freq.current) if freq else None,
        "freq_max_mhz": round(freq.max) if freq and freq.max else None,
        "load_avg_1m": round(load[0], 2) if load else None,
    }


def _memory_status() -> dict:
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024**3), 2),
        "used_gb": round(vm.used / (1024**3), 2),
        "available_gb": round(vm.available / (1024**3), 2),
        "percent": vm.percent,
    }


def _parse_float(raw: str) -> float | None:
    raw = raw.strip()
    try:
        return float(raw)
    except ValueError:
        return None  # e.g. "[N/A]" when a metric isn't supported on this GPU


async def _gpu_status() -> dict:
    """Shell out to `nvidia-smi` fresh on every call rather than keeping an
    NVML handle alive in this long-lived process.

    In-process pynvml.nvmlInit() was found to permanently fail for this
    process specifically under Docker Desktop/WSL2 GPU passthrough (the
    nvidia-container-runtime hook that wraps the container's PID 1 leaves its
    NVML handle broken), even though a brand-new process in the same
    container can always initialize NVML/nvidia-smi successfully. Spawning a
    subprocess per query sidesteps that broken in-process state entirely.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            f"--query-gpu={_NVIDIA_SMI_FIELDS}",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    except (OSError, TimeoutError):  # nvidia-smi missing, or hung
        return {"available": False}

    if proc.returncode != 0 or not stdout:
        return {"available": False}

    devices = []
    for line in stdout.decode().strip().splitlines():
        fields = [f.strip() for f in line.split(",")]
        if len(fields) != 8:
            continue
        name, util_gpu, util_mem, mem_total, mem_used, temperature, power, fan = fields
        mem_total_mib = _parse_float(mem_total)
        mem_used_mib = _parse_float(mem_used)
        devices.append(
            {
                "name": name,
                "util_percent": _parse_float(util_gpu),
                "mem_util_percent": _parse_float(util_mem),
                "vram_total_gb": round(mem_total_mib / 1024, 2) if mem_total_mib is not None else None,
                "vram_used_gb": round(mem_used_mib / 1024, 2) if mem_used_mib is not None else None,
                "temperature_c": _parse_float(temperature),
                "power_w": _parse_float(power),
                "fan_percent": _parse_float(fan),
            }
        )

    if not devices:
        return {"available": False}
    primary = devices[0]
    return {"available": True, **primary, "devices": devices}


async def _llm_status() -> dict:
    """The generation engine now lives in-process (vLLM), so there's no
    remote server to ping - just report the configured model and whether
    init_engine() has finished loading it."""
    return {
        "engine": "vllm",
        "model": settings.vllm_model,
        "quantization": settings.vllm_quantization,
        "max_model_len": settings.llm_num_ctx,
        "ready": llm.is_ready(),
    }


async def _embedding_status() -> dict:
    status = {
        "model": settings.ollama_embed_model,
        "base_url": settings.ollama_base_url,
        "reachable": False,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/ps")
            resp.raise_for_status()
            status["reachable"] = True
    except Exception:  # noqa: BLE001 - Ollama offline shouldn't kill the socket
        pass
    return status


@router.websocket("/ws/system")
async def system_status_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = {
                "cpu": _cpu_status(),
                "memory": _memory_status(),
                "gpu": await _gpu_status(),
                "llm": await _llm_status(),
                "embedding": await _embedding_status(),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(settings.system_ws_interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(Exception):
            await websocket.close()
