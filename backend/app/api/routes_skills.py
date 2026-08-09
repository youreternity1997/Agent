from fastapi import APIRouter

from app.skills.loader import list_skills

router = APIRouter(prefix="/api", tags=["skills"])


@router.get("/skills")
async def get_skills():
    """List available Skill modules for the frontend to render as a dropdown."""
    return list_skills()
