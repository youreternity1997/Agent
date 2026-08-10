"""Local speech-to-text via faster-whisper. Model is loaded once (lazily) and
reused across requests - reloading it per-request would be far too slow.
"""

import tempfile
from pathlib import Path
from threading import Lock

from app.core.config import get_settings

settings = get_settings()

_model = None
_model_lock = Lock()


class TranscribeError(RuntimeError):
    pass


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                _model = WhisperModel(
                    settings.whisper_model_size,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )
    return _model


def transcribe_audio(raw_bytes: bytes, filename: str) -> str:
    if not raw_bytes:
        raise TranscribeError("收到空的音訊檔案")

    suffix = Path(filename).suffix or ".webm"
    try:
        model = _get_model()
    except Exception as exc:  # noqa: BLE001
        raise TranscribeError(f"無法載入語音辨識模型：{exc}") from exc

    # delete=False + manual unlink: on Windows a second reader (faster-whisper's
    # own file open) can't open a file that's still held open by this handle.
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(raw_bytes)
        tmp.close()
        try:
            segments, _info = model.transcribe(tmp.name, beam_size=5)
            text = "".join(segment.text for segment in segments).strip()
        except Exception as exc:  # noqa: BLE001
            raise TranscribeError(f"語音轉文字失敗：{exc}") from exc
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    if not text:
        raise TranscribeError("未辨識出任何文字，請確認錄音內容")
    return text
