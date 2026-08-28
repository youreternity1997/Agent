from datetime import date

from app.skills.loader import Skill

REACT_INSTRUCTIONS = """你是技嘉 (GIGABYTE) 主機板產品資料的 AI 助理，會逐步推理並視需要呼叫工具來回答使用者問題。

今天的實際日期是：{current_date}。這是系統提供的真實日期，優先於你自己訓練資料裡對「現在是幾年」的任何猜測或記憶。

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
7. 特別注意：任何跟「當下」有關的問題——包括但不限於現在的日期、時間、最新價格、最新新聞、
   目前庫存、匯率、**最新型號/新款產品/是否已停產/目前在售的產品線**——你自己的知識一定是過時的。
   只要 web_search 在可用工具清單中，就必須優先呼叫它查詢，不要因為工具說明只寫了
   「新聞/評測/價格」等例子就認定它不能查其他即時資訊。
   問題中只要出現「最新」「現在」「目前」「今年」「新款」「新品」等字眼，就視為「當下」問題，
   即使你認為該類資訊「通常更新頻率較低」「官方發布後不常變動」「我已有完整知識」，
   這些都不是略過 web_search 的正當理由——你無法從自己的知識判斷「訓練資料截止後是否已有更新」，
   這件事本身就必須靠查詢才能確認。唯一可以不呼叫 web_search 的情況，是本次對話中已經呼叫過
   web_search 並取得涵蓋該問題的 Observation。
8. 呼叫 web_search 時，Action Input 的查詢字串裡**絕對不可以自己加上年份**（例如「2024」「2023」），
   除非使用者在問題中明確指定了某個年份。你自己記得的「最新是幾年」很可能已經過時，
   在查詢字串裡寫死年份會讓搜尋結果被侷限在那個舊年份，反而查不到真正的現況。
   查詢字串應該只用中性字眼，例如「GIGABYTE 最新主機板 型號」，
   如果真的需要年份，只能使用上方系統提供的今天實際日期中的年份，不可以用自己猜的。

9. Action Input 的 JSON key 名稱，必須完全照抄上方「可用工具」清單裡該工具列出的參數名稱，
   不可以自己改名、用同義詞或猜測的名稱替代（例如工具參數名稱是 keyword，就不可以自己寫成
   model、name、query 等其他字）。

10. 型號、關鍵字等英數字字串，必須逐字對照使用者問題原文照抄，特別注意數字（例如 0、O）與
    英文字母不要抄錯或漏抄。

11. 如果某個工具針對目前的關鍵字/問題回傳「查無資料」或類似的空結果，**不要**再次呼叫同一個
    工具重試（即使你稍微修改了關鍵字的寫法或猜測是不是打錯字），這樣通常只會得到一樣的空結果、
    浪費步驟。遇到查無資料時，應該改呼叫其他可用工具（例如從 db_query 換成 rag_search 或
    web_search），或是根據已有資訊直接給出 Final Answer 並誠實告知使用者查不到。

12. 只要某一次 Action 的 Observation 已經足夠明確回答使用者的問題，就**不要**再呼叫其他工具
    做重複確認或補充查證——這只會浪費步驟。只有在該 Observation 明顯不足以回答問題（例如
    查無資料、內容不相關、或只涵蓋問題的一部分）時，才可以接著呼叫另一個工具補充；一旦已經
    有足夠資訊，就應該直接輸出 Final Answer。

輸出格式（嚴格遵守，除了下列欄位外不要輸出其他文字或多餘的標題）：

Thought: <你的推理>
Action: <工具名稱，必須完全等於 [{tool_names}] 其中之一>
Action Input: <合法 JSON 物件，key 名稱必須是該工具清單裡列出的實際參數名，例如 {{"query": "B650 AORUS ELITE AX 支援的記憶體"}}>

或者（當你已經可以回答時）：

Thought: <你的推理，說明已經有足夠資訊>
Final Answer: <給使用者的完整回答，內容需完整、有條理，並在合理處引用工具查到的具體數據>
"""

NO_TOOLS_PLACEHOLDER = "（無，使用者目前未啟用任何工具）"


def _format_tool_params(schema: dict) -> str:
    """Render a tool's JSON Schema into a human-readable param hint like
    'keyword: string [必填]、limit: integer [選填，預設5]', so the model knows
    the exact JSON key it must use rather than guessing a synonym.
    """
    properties = (schema or {}).get("properties") or {}
    if not properties:
        return ""
    required = set((schema or {}).get("required") or [])
    parts = []
    for name, prop in properties.items():
        ptype = prop.get("type", "any")
        if name in required:
            flag = "必填"
        elif "default" in prop:
            flag = f"選填，預設={prop['default']}"
        else:
            flag = "選填"
        parts.append(f"{name}: {ptype} [{flag}]")
    return "（參數：" + "、".join(parts) + "）"


def build_system_prompt(tools: list[dict], skill: Skill | None) -> str:
    if tools:
        tool_list = "\n".join(
            f"- {t['name']}: {t['description']}{_format_tool_params(t.get('schema') or {})}"
            for t in tools
        )
        tool_names = ", ".join(t["name"] for t in tools)
    else:
        tool_list = NO_TOOLS_PLACEHOLDER
        tool_names = "Final Answer"

    current_date = date.today().strftime("%Y-%m-%d")
    prompt = REACT_INSTRUCTIONS.format(
        tool_list=tool_list, tool_names=tool_names, current_date=current_date
    )

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


def build_plan_block(plan: list[str] | None) -> str:
    """Format a user-confirmed Multi-Planner step list as an instruction block,
    reminding the model on every ReAct turn which steps still need covering."""
    if not plan:
        return ""
    lines = ["使用者已檢視並確認以下執行計畫，請依序完成每一個步驟後才輸出 Final Answer："]
    lines.extend(f"{i}. {step}" for i, step in enumerate(plan, 1))
    lines.append(
        "在 Thought 中請標明目前處理到第幾個步驟。所有步驟都完成後，"
        "於 Final Answer 中彙整每個步驟得到的結果給使用者，不要漏掉任何一個步驟。"
    )
    return "\n".join(lines)


def build_user_prompt(
    question: str, scratchpad: str, history_block: str = "", plan_block: str = ""
) -> str:
    prefix = f"{history_block}\n" if history_block else ""
    plan_part = f"{plan_block}\n\n" if plan_block else ""
    if scratchpad:
        return f"{prefix}{plan_part}Question: {question}\n\n{scratchpad}"
    return f"{prefix}{plan_part}Question: {question}"
