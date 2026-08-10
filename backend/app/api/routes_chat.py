import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.react_agent import run_react
from app.core.config import get_settings
from app.db.database import get_session
from app.db.models import Conversation, Message

router = APIRouter(prefix="/api", tags=["chat"])
settings = get_settings()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="使用者的問題")
    conversation_id: int = Field(..., description="所屬對話的 id")
    tools: list[str] = Field(default_factory=list, description="前端勾選啟用的 MCP 工具 id 清單")
    skill: str | None = Field(default=None, description="選用的 Skill id")


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _load_history(session: AsyncSession, conversation_id: int) -> list[dict]:
    """Sliding window: only the most recent N messages are sent to the LLM as context."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(settings.llm_context_window_messages)
    )
    rows = (await session.execute(stmt)).scalars().all()
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows if m.content]


async def _trim_stored_history(session: AsyncSession, conversation_id: int) -> None:
    """Storage-side cap: once a conversation grows past the limit, drop the oldest rows."""
    total = (
        await session.execute(
            select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
        )
    ).scalar_one()
    overflow = total - settings.max_stored_messages_per_conversation
    if overflow <= 0:
        return
    oldest_ids = (
        (
            await session.execute(
                select(Message.id)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id.asc())
                .limit(overflow)
            )
        )
        .scalars()
        .all()
    )
    if oldest_ids:
        await session.execute(delete(Message).where(Message.id.in_(oldest_ids)))


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    conversation = await session.get(Conversation, req.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="對話不存在")

    user_msg = Message(conversation_id=conversation.id, role="user", content=req.message)
    session.add(user_msg)
    conversation.updated_at = func.now()
    await session.commit()
    await session.refresh(user_msg)

    # Sliding window over prior turns; drop the user turn just persisted above since
    # it's passed separately as `question` (it's always the newest row here).
    history = (await _load_history(session, conversation.id))[:-1]

    async def event_stream():
        final_answer = ""
        steps: list[dict] = []
        yield _sse_event({"type": "meta", "user_message_id": user_msg.id})
        try:
            async for event in run_react(
                question=req.message,
                history=history,
                selected_tools=req.tools,
                skill_id=req.skill,
            ):
                event_type = event.get("type")
                if event_type == "thought":
                    steps.append({"kind": "thought", "step": event.get("step"), "content": event.get("content")})
                elif event_type == "action":
                    steps.append(
                        {
                            "kind": "action",
                            "step": event.get("step"),
                            "tool": event.get("tool"),
                            "input": event.get("input"),
                        }
                    )
                elif event_type == "observation":
                    steps.append(
                        {"kind": "observation", "step": event.get("step"), "content": event.get("content")}
                    )
                elif event_type == "final_answer":
                    final_answer = event.get("content", "")
                elif event_type == "error":
                    steps.append({"kind": "error", "content": event.get("content")})
                yield _sse_event(event)
        except Exception as exc:  # noqa: BLE001 - never let a raw 500 kill the stream
            steps.append({"kind": "error", "content": f"未預期的錯誤：{exc}"})
            yield _sse_event({"type": "error", "content": f"未預期的錯誤：{exc}"})
        finally:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=final_answer,
                steps=steps,
            )
            session.add(assistant_msg)
            conversation.updated_at = func.now()
            await _trim_stored_history(session, conversation.id)
            await session.commit()
            await session.refresh(assistant_msg)
            yield _sse_event({"type": "meta", "assistant_message_id": assistant_msg.id})
            yield _sse_event({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
