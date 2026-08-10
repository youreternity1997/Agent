from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Conversation, Message

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

DEFAULT_PAGE_SIZE = 50


class CreateConversationRequest(BaseModel):
    title: str = Field(default="新對話", max_length=200)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


def _conversation_dict(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


def _message_dict(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "steps": msg.steps,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("")
async def list_conversations(session: AsyncSession = Depends(get_session)):
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    conversations = (await session.execute(stmt)).scalars().all()
    return [_conversation_dict(c) for c in conversations]


@router.post("")
async def create_conversation(
    req: CreateConversationRequest, session: AsyncSession = Depends(get_session)
):
    conv = Conversation(title=req.title)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return _conversation_dict(conv)


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    req: RenameConversationRequest,
    session: AsyncSession = Depends(get_session),
):
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="對話不存在")
    conv.title = req.title
    await session.commit()
    await session.refresh(conv)
    return _conversation_dict(conv)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, session: AsyncSession = Depends(get_session)):
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="對話不存在")
    await session.delete(conv)
    await session.commit()
    return {"status": "deleted", "id": conversation_id}


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: int,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    session: AsyncSession = Depends(get_session),
):
    """Return up to `limit` messages, newest-first internally then re-sorted to
    chronological order for the response. Pass `before_id` (the oldest message id
    currently shown) to page further back in history - this is what the frontend's
    "load older" sliding window uses.
    """
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="對話不存在")

    limit = max(1, min(limit, 200))
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    stmt = stmt.order_by(Message.id.desc()).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    rows.reverse()

    return {
        "messages": [_message_dict(m) for m in rows],
        "has_more": await _has_older_messages(session, conversation_id, rows[0].id if rows else None),
    }


async def _has_older_messages(session: AsyncSession, conversation_id: int, oldest_id: int | None) -> bool:
    if oldest_id is None:
        return False
    stmt = (
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id, Message.id < oldest_id)
    )
    count = (await session.execute(stmt)).scalar_one()
    return count > 0


@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: int, message_id: int, session: AsyncSession = Depends(get_session)
):
    msg = await session.get(Message, message_id)
    if msg is None or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="訊息不存在")
    await session.execute(delete(Message).where(Message.id == message_id))
    await session.commit()
    return {"status": "deleted", "id": message_id}
