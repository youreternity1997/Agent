from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_conversations import router as conversations_router
from app.api.routes_documents import router as documents_router
from app.api.routes_skills import router as skills_router
from app.api.routes_tools import router as tools_router
from app.api.routes_transcribe import router as transcribe_router
from app.api.routes_ws_system import router as ws_system_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="GIGABYTE AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(tools_router)
app.include_router(skills_router)
app.include_router(conversations_router)
app.include_router(documents_router)
app.include_router(transcribe_router)
app.include_router(ws_system_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.ollama_model}
