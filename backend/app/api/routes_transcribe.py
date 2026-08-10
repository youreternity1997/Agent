import asyncio

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.transcribe import TranscribeError, transcribe_audio

router = APIRouter(prefix="/api", tags=["transcribe"])


@router.post("/transcribe")
async def transcribe_endpoint(audio: UploadFile):
    raw = await audio.read()
    try:
        text = await asyncio.to_thread(transcribe_audio, raw, audio.filename or "audio.webm")
    except TranscribeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"text": text}
