from fastapi import APIRouter, HTTPException

from app.mcp_client.client import list_mcp_tools

router = APIRouter(prefix="/api", tags=["tools"])


@router.get("/tools")
async def get_tools():
    """List MCP tools available for the frontend to render as checkboxes."""
    try:
        return await list_mcp_tools()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"無法連線到 MCP 工具伺服器：{exc}",
        ) from exc
