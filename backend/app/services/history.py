"""Shared conversation-history loading, used by both the chat endpoint and
the planner endpoint so the two stay consistent about what "recent context"
means.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Message

settings = get_settings()


async def load_recent_history(session: AsyncSession, conversation_id: int) -> list[dict]:
    """Sliding window: only the most recent N messages, oldest-first, as {role, content} dicts."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(settings.llm_context_window_messages)
    )
    rows = (await session.execute(stmt)).scalars().all()
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows if m.content]
