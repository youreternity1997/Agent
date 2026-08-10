from app.skills.loader import Skill

REACT_INSTRUCTIONS = """你是技嘉 (GIGABYTE) 主機板產品資料的 AI 助理，會逐步推理並視需要呼叫工具來回答使用者問題。

可用工具：
{tool_list}

規則：
1. 每次回覆都必須先寫 Thought，說明你目前的推理與下一步打算做什麼。在 Thought 中，你必須明確評估：
   「上方工具清單中，有沒有工具可能幫助我更準確地回答這個問題？」對每一個可用工具都要考慮一次，
   不要只因為工具的說明文字沒有『明確列出』這個情境，就直接排除它——工具說明只是舉例，不是完整清單。
   只有在你確定「就算呼叫工具，也不可能得到比你自己已知更好的答案」時，才不使用工具直接作答。
2. 如果還需要更多資訊，接著輸出 Action 與 Action Input，然後**立刻停止**，不要自己編造 "Observation:"
   （那是系統實際呼叫工具後才會提供給你的真實結果，你自己生成的一律無效）。
3. 如果目前資訊已足夠回答使用者問題，改為輸出 Final Answer，不要再輸出 Action。
4. 只要你在本次對話中呼叫過任何工具，撰寫 Final Answer 時就只能根據實際收到的 Observation 內容作答，
   不可以用你自己訓練資料中記得的型號、規格、日期、價格等具體事實去補充或延伸 Observation 沒有出現的內容——
   即使那些「聽起來很合理」或是你很確定。如果 Observation 涵蓋不到使用者問題的某個部分
   （例如使用者問「最新」，但工具查到的資料只到某個年份/版本），必須在 Final Answer 中誠實說明
   「目前工具查到的最新資料是 X，可能不代表現況」，絕對不可以自己編造更新的型號、日期或數字讓答案顯得更完整。
5. 如果目前沒有任何可用工具（上方工具清單為空），代表使用者沒有勾選任何 MCP 工具，
   才允許直接依你自己的知識作答，並在回答中誠實提醒使用者「目前未啟用外部工具，以下內容可能不是最新資訊」。
6. 只能使用繁體中文回答。
7. 特別注意：任何跟「當下」有關的問題（例如現在的日期、時間、最新價格、最新新聞、目前庫存、匯率等），
   你自己的知識一定是過時的。只要 web_search 在可用工具清單中，就應該優先呼叫它查詢，
   不要因為工具說明只寫了「新聞/評測/價格」等例子就認定它不能查其他即時資訊。

輸出格式（嚴格遵守，除了下列欄位外不要輸出其他文字或多餘的標題）：

Thought: <你的推理>
Action: <工具名稱，必須完全等於 [{tool_names}] 其中之一>
Action Input: <合法 JSON 物件，例如 {{"query": "B650 AORUS ELITE AX 支援的記憶體"}}>

或者（當你已經可以回答時）：

Thought: <你的推理，說明已經有足夠資訊>
Final Answer: <給使用者的完整回答，內容需完整、有條理，並在合理處引用工具查到的具體數據>
"""

NO_TOOLS_PLACEHOLDER = "（無，使用者目前未啟用任何工具）"


def build_system_prompt(tools: list[dict], skill: Skill | None) -> str:
    if tools:
        tool_list = "\n".join(f"- {t['name']}: {t['description']}" for t in tools)
        tool_names = ", ".join(t["name"] for t in tools)
    else:
        tool_list = NO_TOOLS_PLACEHOLDER
        tool_names = "Final Answer"

    prompt = REACT_INSTRUCTIONS.format(tool_list=tool_list, tool_names=tool_names)

    if skill:
        prompt += f"\n# 角色設定與領域知識（Skill: {skill.title}）\n{skill.content}\n"

    return prompt


def build_history_block(history: list[dict]) -> str:
    """Format the sliding-window of prior conversation turns as plain text context."""
    if not history:
        return ""
    lines = ["以下是先前的對話紀錄（僅供參考上下文，不需要重新回答）："]
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {turn['content']}")
    return "\n".join(lines) + "\n"


def build_user_prompt(question: str, scratchpad: str, history_block: str = "") -> str:
    prefix = f"{history_block}\n" if history_block else ""
    if scratchpad:
        return f"{prefix}Question: {question}\n\n{scratchpad}"
    return f"{prefix}Question: {question}"
