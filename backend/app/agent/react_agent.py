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

from app.agent.prompts import (
    build_history_block,
    build_plan_block,
    build_system_prompt,
    build_user_prompt,
)
from app.core.config import get_settings
from app.core.llm import LLMError, chat_stream, count_prompt_tokens
from app.mcp_client.client import call_mcp_tool, mcp_session
from app.skills.loader import get_skill

settings = get_settings()

TOOL_CALL_TIMEOUT_SECONDS = 60.0
LLM_STREAM_IDLE_TIMEOUT_SECONDS = 90.0

CONTEXT_OUTPUT_RESERVE_TOKENS = max(768, settings.llm_max_tokens)

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
        raw_input = input_match.group(1).strip()
        return {"thought": thought, "action": action, "raw_input": raw_input}

    return {"thought": thought, "final_answer": text.strip()}


def _normalize_action_input(action: str, parsed: dict) -> dict:
    """Repair a single wrong JSON key for the tool's primary parameter.

    The model occasionally invents a plausible-but-wrong key (e.g. {"model": "..."}
    for db_query's "keyword" param) even though it produced otherwise-valid JSON,
    which would bypass the raw-text fallback below and fail tool-side validation.
    Only remap when there's exactly one key and it isn't already the expected one,
    so legitimate multi-param calls are left untouched.
    """
    primary = _PRIMARY_PARAM.get(action)
    if primary and primary not in parsed and len(parsed) == 1:
        ((only_key, only_value),) = parsed.items()
        return {primary: only_value}
    return parsed


def _drop_oldest_scratchpad_block(scratchpad: str) -> str:
    """Discard the oldest Thought/Action/Observation block, keeping the rest -
    used to bring a too-large prompt back under the context budget without
    losing the most recent (most relevant) reasoning."""
    blocks = [b for b in scratchpad.split("\n\n") if b.strip()]
    if len(blocks) <= 1:
        return ""
    return "\n\n".join(blocks[1:]) + "\n\n"


def _parse_action_input(action: str, raw_input: str) -> dict:
    # Trim anything after a clean JSON object if the model kept rambling.
    candidate = raw_input.strip()
    brace_match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return _normalize_action_input(action, parsed)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: treat the raw text as the tool's primary string parameter.
    param_name = _PRIMARY_PARAM.get(action, "query")
    cleaned = raw_input.strip().strip('"')
    return {param_name: cleaned}


async def _stream_with_timeout(
    messages: list[dict], stop: list[str] | None = None
) -> AsyncGenerator[str, None]:
    """chat_stream() wrapped with an idle-gap timeout between chunks, so a
    stalled generation (e.g. vLLM's scheduler stuck under a tight KV cache -
    observed sitting at 0% GPU utilization producing nothing, with no
    exception ever raised) surfaces as an LLMError instead of hanging the
    caller forever."""
    stream = chat_stream(messages, stop=stop)
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=LLM_STREAM_IDLE_TIMEOUT_SECONDS)
            except StopAsyncIteration:
                return
            yield chunk
    except TimeoutError as exc:
        await stream.aclose()
        raise LLMError(
            f"本地 LLM 生成超過 {int(LLM_STREAM_IDLE_TIMEOUT_SECONDS)} 秒沒有新內容，"
            "疑似推論引擎卡住，已中止此次請求，請稍後再試一次。"
        ) from exc


_FORCE_ANSWER_NOTICE = (
    "系統通知：你剛才嘗試呼叫的工具目前無法使用（已使用過或不存在），工具呼叫功能已被系統暫時停用。"
    "請根據以上已經取得的 Observation 內容，直接輸出 Final Answer，完整回答使用者的問題，"
    "不要再輸出 Thought 或 Action。"
)


async def _force_final_answer(
    question: str,
    scratchpad: str,
    history_block: str,
    plan_block: str,
    skill,
    step: int,
    tools_exhausted: bool = False,
) -> AsyncGenerator[dict, None]:
    """Bypass tool-calling entirely and ask the model once more for a Final
    Answer only. Used right after the model tries to call a tool that isn't
    available (already used, or never existed) - relying on it to notice the
    shrunk tool list and self-correct on its own has been observed to fail in
    practice (it kept re-issuing the identical blocked call 3 times in a row
    in one real trace, burning steps despite already having enough
    information in the scratchpad to answer). This forces the model into "no
    tools available" mode with an extra directive telling it to stop and
    answer now, instead of letting it keep flailing until step_limit.

    `tools_exhausted` must be True whenever a real Observation already exists
    in the scratchpad (i.e. some tool call already succeeded this
    conversation) - otherwise build_system_prompt's default "no tools ever
    enabled" framing actively misleads the model into claiming tools were
    never enabled and answering from its own (possibly stale) knowledge
    instead of the Observation that's sitting right there. Observed in
    practice: the plain _FORCE_ANSWER_NOTICE text in the scratchpad alone
    was not enough to override that framing.
    """
    forced_system_prompt = build_system_prompt([], skill, tools_exhausted=tools_exhausted)
    forced_user_prompt = build_user_prompt(
        question, scratchpad + f"\n{_FORCE_ANSWER_NOTICE}\n", history_block, plan_block
    )
    messages = [
        {"role": "system", "content": forced_system_prompt},
        {"role": "user", "content": forced_user_prompt},
    ]

    raw_parts: list[str] = []
    try:
        async for chunk in _stream_with_timeout(messages):
            raw_parts.append(chunk)
            yield {"type": "delta", "content": chunk, "step": step}
    except LLMError as exc:
        yield {"type": "error", "content": str(exc)}
        return
    raw = "".join(raw_parts)

    parsed = _parse_llm_output(raw)
    yield {"type": "final_answer", "content": parsed.get("final_answer") or raw.strip(), "step": step}


async def run_react(
    question: str,
    selected_tools: list[str],
    skill_id: str | None,
    history: list[dict] | None = None,
    plan: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    """`plan` is the Multi-Planner's user-confirmed (possibly hand-edited) step
    list, if any - a question that was judged simple enough to answer directly
    (e.g. small talk) has no plan, and this behaves exactly as a plain ReAct run.
    """
    skill = get_skill(skill_id)
    history_block = build_history_block(history or [])
    plan_block = build_plan_block(plan)
    step_limit = settings.max_react_steps
    if plan:
        step_limit = max(step_limit, min(len(plan) * 3, 24))
    stack = AsyncExitStack()
    session = None
    tool_descs: list[dict] = []

    try:
        if selected_tools:
            try:
                session = await stack.enter_async_context(mcp_session())
                available = (await session.list_tools()).tools
                tool_descs = [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "schema": t.inputSchema or {},
                    }
                    for t in available
                    if t.name in selected_tools
                ]
            except Exception as exc:  # noqa: BLE001
                yield {"type": "error", "content": f"無法啟動 MCP 工具伺服器：{exc}"}
                return

        scratchpad = ""
        used_tool_names: set[str] = set()

        if plan:
            yield {"type": "plan", "steps": plan}

        for step in range(1, step_limit + 1):
            available_tool_descs = [t for t in tool_descs if t["name"] not in used_tool_names]
            tools_exhausted = bool(tool_descs) and not available_tool_descs
            system_prompt = build_system_prompt(available_tool_descs, skill, tools_exhausted=tools_exhausted)
            enabled_names = {t["name"] for t in available_tool_descs}

            user_prompt = build_user_prompt(question, scratchpad, history_block, plan_block)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            try:
                budget = settings.llm_num_ctx - CONTEXT_OUTPUT_RESERVE_TOKENS
                while scratchpad and count_prompt_tokens(messages) > budget:
                    scratchpad = _drop_oldest_scratchpad_block(scratchpad)
                    user_prompt = build_user_prompt(question, scratchpad, history_block, plan_block)
                    messages[-1] = {"role": "user", "content": user_prompt}
            except LLMError:
                pass  # engine not ready - chat_stream's own check below will raise with the real reason

            raw_parts: list[str] = []
            try:
                async for chunk in _stream_with_timeout(messages, stop=["Observation:"]):
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

            action_blocked = action not in enabled_names or session is None
            if action_blocked:
                if action in used_tool_names:
                    observation = (
                        f"系統提示：工具「{action}」已經使用過，每個工具在本次對話中只能呼叫一次，"
                        "目前已從可用工具清單移除，不會再次執行。"
                        "請從剩餘可用工具清單中選擇其他工具，或直接根據已有資訊給出 Final Answer。"
                    )
                else:
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
                used_tool_names.add(action)

            yield {"type": "observation", "content": observation, "step": step}

            scratchpad += (
                f"Thought: {parsed.get('thought', '')}\n"
                f"Action: {action}\n"
                f"Action Input: {json.dumps(action_input, ensure_ascii=False)}\n"
                f"Observation: {observation}\n\n"
            )
            if action_blocked:
                async for event in _force_final_answer(
                    question, scratchpad, history_block, plan_block, skill, step,
                    tools_exhausted=bool(used_tool_names),
                ):
                    yield event
                return

        yield {
            "type": "final_answer",
            "content": (
                "已達到最大推理步數上限，尚未得到明確結論。"
                "以下是目前已收集到的資訊，僅供參考：\n\n" + scratchpad[-2000:]
            ),
            "step": step_limit,
        }
    finally:
        await stack.aclose()
