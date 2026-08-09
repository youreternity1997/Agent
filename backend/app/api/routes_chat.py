import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.react_agent import run_react

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="使用者的問題")
    tools: list[str] = Field(default_factory=list, description="前端勾選啟用的 MCP 工具 id 清單")
    skill: str | None = Field(default=None, description="選用的 Skill id")


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    async def event_stream():
        try:
            async for event in run_react(
                question=req.message,
                selected_tools=req.tools,
                skill_id=req.skill,
            ):
                yield _sse_event(event)
        except Exception as exc:  # noqa: BLE001 - never let a raw 500 kill the stream
            yield _sse_event({"type": "error", "content": f"未預期的錯誤：{exc}"})
        finally:
            yield _sse_event({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
