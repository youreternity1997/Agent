"""Loads Skill modules: Markdown files with YAML frontmatter under app/skills/.

Each skill is domain-knowledge / system-prompt content that gets injected into
the ReAct system prompt, letting the frontend switch the agent's "persona"
(e.g. general Q&A vs. compatibility checking vs. troubleshooting) without any
code changes — just drop a new .md file in this directory.
"""

from dataclasses import dataclass
from functools import lru_cache

import yaml

from app.core.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class Skill:
    id: str
    title: str
    description: str
    content: str


def _parse_skill_file(path) -> Skill:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Skill 檔案 {path} 缺少 YAML frontmatter")

    _, frontmatter_raw, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter_raw) or {}
    return Skill(
        id=meta.get("id", path.stem),
        title=meta.get("title", path.stem),
        description=meta.get("description", ""),
        content=body.strip(),
    )


@lru_cache
def load_skills() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for path in sorted(settings.skills_dir.glob("*.md")):
        skill = _parse_skill_file(path)
        skills[skill.id] = skill
    return skills


def get_skill(skill_id: str | None) -> Skill | None:
    if not skill_id:
        return None
    return load_skills().get(skill_id)


def list_skills() -> list[dict]:
    return [
        {"id": s.id, "title": s.title, "description": s.description}
        for s in load_skills().values()
    ]
