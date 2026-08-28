"""Multi-Planner: decides whether a user's message needs to be broken into an
explicit multi-step plan (a compound/research task) or can just be answered
directly (small talk, a single simple question) - and if so, drafts that plan
as an ordered list of step descriptions for the user to review, edit, delete
from, or add to in the frontend before the ReAct agent (run_react) executes
the confirmed plan.

This is a separate, lightweight LLM call from the ReAct loop itself: it asks
for one JSON object, not a multi-turn Thought/Action trace.
"""

import json
import re
from dataclasses import dataclass, field

from app.core.llm import LLMError, chat_complete
from app.skills.loader import Skill

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

PLANNER_INSTRUCTIONS = """你是任務規劃助理，負責判斷使用者的訊息是否需要拆解成多個執行步驟，
並在需要時草擬一份步驟計畫。這份計畫之後會顯示給使用者檢視、編輯（刪除/修改/新增步驟），
使用者確認後才會交給另一個具備工具呼叫能力的 Agent 依序執行，所以步驟必須寫得清楚具體。

可用工具：
{tool_list}

判斷原則：
1. 如果使用者的訊息只是閒聊、打招呼、情緒抒發、單一簡單問題，或原本就只需要一步就能
   回答完（例如單純問候、簡單的名詞定義、只問單一明確型號的單一規格），視為「不需要計畫」。
2. 如果使用者的目標需要多個不同步驟才能完成——例如需要查詢多筆資料再比較、需要先查詢
   再彙整結論、涉及多個型號/多個條件、或使用者的措辭本身就是一個多階段任務——才需要拆解。
3. 每個步驟必須是具體、可獨立執行的子任務描述（例如「查詢 B650 AORUS ELITE AX 的記憶體
   規格」「查詢 X670E AORUS MASTER 的記憶體規格」「比較兩者差異並整理結論」），不要寫得
   太籠統（例如不要只寫「查資料」）。
4. 步驟數量抓 2 到 6 步之間，不要為了拆解而拆解、也不要把單一步驟拆得過細。
5. 只能使用繁體中文。

請只輸出一個 JSON 物件，不要有任何其他文字、說明或 Markdown 標記：
{{"needs_plan": true 或 false, "steps": ["步驟一", "步驟二", ...]}}
不需要計畫時，"needs_plan" 為 false，"steps" 給空陣列 []。
"""


@dataclass(frozen=True)
class PlanResult:
    needs_plan: bool
    steps: list[str] = field(default_factory=list)


def _format_tool_list(tools: list[dict]) -> str:
    if not tools:
        return "（無，使用者目前未啟用任何工具，計畫步驟不應假設有工具可查）"
    return "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in tools)


def _build_system_prompt(tools: list[dict], skill: Skill | None) -> str:
    prompt = PLANNER_INSTRUCTIONS.format(tool_list=_format_tool_list(tools))
    if skill:
        prompt += f"\n# 角色設定與領域知識（Skill: {skill.title}）\n{skill.content}\n"
    return prompt


def _parse_plan_output(text: str) -> PlanResult:
    candidate = text.strip()
    match = _JSON_BLOCK_RE.search(candidate)
    if match:
        candidate = match.group(0)
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        # Model didn't follow the format - degrade to "no plan" rather than
        # blocking the user from getting any answer at all.
        return PlanResult(needs_plan=False, steps=[])

    if not isinstance(data, dict):
        return PlanResult(needs_plan=False, steps=[])

    raw_steps = data.get("steps") or []
    steps = [str(s).strip() for s in raw_steps if str(s).strip()]
    needs_plan = bool(data.get("needs_plan")) and len(steps) > 0
    return PlanResult(needs_plan=needs_plan, steps=steps)


async def generate_plan(
    question: str,
    tool_descs: list[dict],
    skill: Skill | None,
    history_block: str = "",
) -> PlanResult:
    system_prompt = _build_system_prompt(tool_descs, skill)
    prefix = f"{history_block}\n" if history_block else ""
    user_prompt = f"{prefix}使用者訊息：{question}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        raw = await chat_complete(messages)
    except LLMError:
        # Planning is best-effort - fall back to a direct (unplanned) answer
        # rather than erroring out the whole request.
        return PlanResult(needs_plan=False, steps=[])
    return _parse_plan_output(raw)
