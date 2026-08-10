"""WebSocket that periodically pushes host hardware status (CPU/RAM/GPU) and
the local Ollama model status, so the frontend sidebar can show it live.

This is a separate channel from the chat SSE stream (/api/chat) - it never
touches the ReAct loop.
"""

import asyncio
from contextlib import suppress

import httpx
import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings

router = APIRouter(tags=["system"])
settings = get_settings()

try:
    import pynvml

    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:  # noqa: BLE001 - no NVIDIA GPU/driver/pynvml, degrade gracefully
    _NVML_AVAILABLE = False


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


def _gpu_status() -> dict:
    if not _NVML_AVAILABLE:
        return {"available": False}
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        devices = []
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()

            temperature = None
            with suppress(Exception):
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

            power_w = None
            with suppress(Exception):
                power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)

            fan_percent = None
            with suppress(Exception):
                fan_percent = pynvml.nvmlDeviceGetFanSpeed(handle)

            devices.append(
                {
                    "name": name,
                    "util_percent": util.gpu,
                    "mem_util_percent": util.memory,
                    "vram_total_gb": round(mem.total / (1024**3), 2),
                    "vram_used_gb": round(mem.used / (1024**3), 2),
                    "temperature_c": temperature,
                    "power_w": power_w,
                    "fan_percent": fan_percent,
                }
            )
        primary = devices[0]
        return {"available": True, **primary, "devices": devices}
    except Exception:  # noqa: BLE001
        return {"available": False}


async def _ollama_status() -> dict:
    status = {
        "configured_model": settings.ollama_model,
        "embed_model": settings.ollama_embed_model,
        "base_url": settings.ollama_base_url,
        "loaded_models": [],
        "reachable": False,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/ps")
            resp.raise_for_status()
            data = resp.json()
            status["reachable"] = True
            status["loaded_models"] = [
                {
                    "name": m.get("name"),
                    "size_gb": round(m.get("size", 0) / (1024**3), 2),
                    "vram_gb": round(m.get("size_vram", 0) / (1024**3), 2),
                    "expires_at": m.get("expires_at"),
                }
                for m in data.get("models", [])
            ]
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
                "gpu": _gpu_status(),
                "ollama": await _ollama_status(),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(settings.system_ws_interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(Exception):
            await websocket.close()
