from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import generate_plan
from app.agent.prompts import build_history_block
from app.db.database import get_session
from app.db.models import Conversation
from app.mcp_client.client import list_mcp_tools
from app.services.history import load_recent_history
from app.skills.loader import get_skill

router = APIRouter(prefix="/api", tags=["plan"])


class PlanRequest(BaseModel):
    message: str = Field(..., min_length=1, description="使用者的問題/目標")
    conversation_id: int = Field(..., description="所屬對話的 id")
    tools: list[str] = Field(default_factory=list, description="前端勾選啟用的 MCP 工具 id 清單")
    skill: str | None = Field(default=None, description="選用的 Skill id")


@router.post("/plan")
async def plan_endpoint(req: PlanRequest, session: AsyncSession = Depends(get_session)):
    """Multi-Planner preview: given a user message, decide whether it needs
    breaking into steps and, if so, draft them. This never writes to the
    database - the actual user/assistant messages are only persisted once the
    (possibly user-edited) plan is confirmed and sent to /api/chat.
    """
    conversation = await session.get(Conversation, req.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="對話不存在")

    history = await load_recent_history(session, conversation.id)
    history_block = build_history_block(history)
    skill = get_skill(req.skill)

    tool_descs: list[dict] = []
    if req.tools:
        try:
            all_tools = await list_mcp_tools()
            tool_descs = [t for t in all_tools if t["name"] in req.tools]
        except Exception:  # noqa: BLE001 - planning degrades to "no plan" without tools
            tool_descs = []

    result = await generate_plan(req.message, tool_descs, skill, history_block)
    return {"needs_plan": result.needs_plan, "steps": result.steps}
