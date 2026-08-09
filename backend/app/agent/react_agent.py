"""The ReAct reasoning loop.

At each step: ask the local LLM for a Thought (+ either an Action/Action Input
or a Final Answer) -> if it chose an action, call the matching MCP tool ->
feed the tool's Observation back into the scratchpad -> repeat, until the
model returns a Final Answer or MAX_REACT_STEPS is reached. Every step is
yielded as an event dict so the API layer can stream it to the frontend via SSE.
"""

import asyncio
import json
import re
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from typing import Any

from app.agent.prompts import build_system_prompt, build_user_prompt
from app.core.config import get_settings
from app.core.llm import LLMError, chat_stream
from app.mcp_client.client import call_mcp_tool, mcp_session
from app.skills.loader import get_skill

settings = get_settings()

TOOL_CALL_TIMEOUT_SECONDS = 60.0

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=\n\s*(?:Action:|Final Answer:)|\Z)", re.DOTALL)
_ACTION_RE = re.compile(r"Action:\s*(.*)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)

_PRIMARY_PARAM = {
    "web_search": "query",
    "rag_search": "query",
    "db_query": "keyword",
}


def _parse_llm_output(text: str) -> dict[str, Any]:
    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else None

    final_match = _FINAL_ANSWER_RE.search(text)
    if final_match:
        return {"thought": thought, "final_answer": final_match.group(1).strip()}

    action_match = _ACTION_RE.search(text)
    input_match = _ACTION_INPUT_RE.search(text)
    if action_match and input_match:
        action = action_match.group(1).strip()
        # Action line is matched non-greedily up to end-of-line; Action Input
        # captures everything after, which may include trailing chatter - keep
        # only the first line/JSON blob.
        raw_input = input_match.group(1).strip()
        return {"thought": thought, "action": action, "raw_input": raw_input}

    # Model didn't follow the format - degrade gracefully to a final answer
    # rather than erroring out the whole conversation.
    return {"thought": thought, "final_answer": text.strip()}


def _parse_action_input(action: str, raw_input: str) -> dict:
    # Trim anything after a clean JSON object if the model kept rambling.
    candidate = raw_input.strip()
    brace_match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: treat the raw text as the tool's primary string parameter.
    param_name = _PRIMARY_PARAM.get(action, "query")
    cleaned = raw_input.strip().strip('"')
    return {param_name: cleaned}


async def run_react(
    question: str,
    selected_tools: list[str],
    skill_id: str | None,
) -> AsyncGenerator[dict, None]:
    skill = get_skill(skill_id)
    stack = AsyncExitStack()
    session = None
    tool_descs: list[dict] = []

    try:
        if selected_tools:
            try:
                session = await stack.enter_async_context(mcp_session())
                available = (await session.list_tools()).tools
                tool_descs = [
                    {"name": t.name, "description": t.description or ""}
                    for t in available
                    if t.name in selected_tools
                ]
            except Exception as exc:  # noqa: BLE001
                yield {"type": "error", "content": f"無法啟動 MCP 工具伺服器：{exc}"}
                return

        system_prompt = build_system_prompt(tool_descs, skill)
        enabled_names = {t["name"] for t in tool_descs}
        scratchpad = ""

        for step in range(1, settings.max_react_steps + 1):
            user_prompt = build_user_prompt(question, scratchpad)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            raw_parts: list[str] = []
            try:
                async for chunk in chat_stream(messages, stop=["Observation:"]):
                    raw_parts.append(chunk)
                    yield {"type": "delta", "content": chunk, "step": step}
            except LLMError as exc:
                yield {"type": "error", "content": str(exc)}
                return
            raw = "".join(raw_parts)

            parsed = _parse_llm_output(raw)

            if parsed.get("thought"):
                yield {"type": "thought", "content": parsed["thought"], "step": step}

            if "final_answer" in parsed:
                yield {"type": "final_answer", "content": parsed["final_answer"], "step": step}
                return

            action = parsed["action"]
            action_input = _parse_action_input(action, parsed["raw_input"])
            yield {"type": "action", "tool": action, "input": action_input, "step": step}

            if action not in enabled_names or session is None:
                available_str = ", ".join(sorted(enabled_names)) or "(無)"
                observation = (
                    f"錯誤：工具「{action}」未啟用或不存在。目前可用工具：{available_str}。"
                    "請根據已知資訊直接給出 Final Answer，或改用可用工具。"
                )
            else:
                try:
                    observation = await asyncio.wait_for(
                        call_mcp_tool(session, action, action_input),
                        timeout=TOOL_CALL_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    observation = (
                        f"工具「{action}」執行超過 {int(TOOL_CALL_TIMEOUT_SECONDS)} 秒仍未回應，已中止。"
                        "請根據已知資訊直接給出 Final Answer，或改用其他工具。"
                    )
                except Exception as exc:  # noqa: BLE001
                    observation = f"工具執行時發生錯誤：{exc}"

            yield {"type": "observation", "content": observation, "step": step}

            scratchpad += (
                f"Thought: {parsed.get('thought', '')}\n"
                f"Action: {action}\n"
                f"Action Input: {json.dumps(action_input, ensure_ascii=False)}\n"
                f"Observation: {observation}\n\n"
            )

        yield {
            "type": "final_answer",
            "content": (
                "已達到最大推理步數上限，尚未得到明確結論。"
                "以下是目前已收集到的資訊，僅供參考：\n\n" + scratchpad[-2000:]
            ),
            "step": settings.max_react_steps,
        }
    finally:
        await stack.aclose()
