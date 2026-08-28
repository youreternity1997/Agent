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

# Floor kept free for the model's own reply so a context-window-sized prompt
# doesn't starve generation down to 0 tokens (vLLM then rejects the request
# outright with a "maximum context length" error rather than just truncating
# the reply). A multi-step Multi-Planner run is the main thing that pushes
# the scratchpad this large - several large tool observations pile up across
# its extra ReAct turns.
CONTEXT_OUTPUT_RESERVE_TOKENS = 768

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=\n\s*(?:Action:|Final Answer:)|\Z)", re.DOTALL)
_ACTION_RE = re.compile(r"Action:\s*(.*)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)

_PRIMARY_PARAM = {
    "web_search": "query",
    "rag_search": "query",
    "db_query": "keyword",
}

_NO_RESULT_MARKERS = ("沒有找到", "查無")


def _looks_like_no_result(observation: str) -> bool:
    return any(marker in observation for marker in _NO_RESULT_MARKERS)


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
    # A multi-step plan needs more ReAct turns than a single-shot answer -
    # scale the budget with the step count instead of hard-coding a bigger
    # constant, but keep an upper bound so a runaway plan can't loop forever.
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

        system_prompt = build_system_prompt(tool_descs, skill)
        enabled_names = {t["name"] for t in tool_descs}
        scratchpad = ""
        last_action: str | None = None
        last_action_failed = False
        # Full-run memory of every (tool, exact input) pair already called -
        # a Multi-Planner run gives the model many more turns to work with,
        # which makes it more likely to re-issue the *identical* call (seen
        # in practice: retrying the same web_search query verbatim several
        # times because the results didn't contain the exact phrase it
        # wanted). Since these tools are read-only lookups, an identical
        # input can only ever produce the same observation again, so repeats
        # are short-circuited without re-hitting the (often slow) tool.
        seen_action_keys: set[tuple[str, str]] = set()

        if plan:
            yield {"type": "plan", "steps": plan}

        for step in range(1, step_limit + 1):
            user_prompt = build_user_prompt(question, scratchpad, history_block, plan_block)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Keep the prompt within the context window: if accumulated tool
            # observations have pushed it too close to llm_num_ctx, drop the
            # oldest scratchpad blocks (oldest first) until there's enough
            # room left for a reply, instead of letting vLLM reject the
            # request outright.
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

            action_key = (action, json.dumps(action_input, ensure_ascii=False, sort_keys=True))

            if action not in enabled_names or session is None:
                available_str = ", ".join(sorted(enabled_names)) or "(無)"
                observation = (
                    f"錯誤：工具「{action}」未啟用或不存在。目前可用工具：{available_str}。"
                    "請根據已知資訊直接給出 Final Answer，或改用可用工具。"
                )
            elif action_key in seen_action_keys:
                observation = (
                    f"系統提示：你已經用完全相同的參數呼叫過「{action}」，"
                    "重複呼叫只會得到一模一樣的結果，不會有新資訊，因此這次系統沒有再實際執行。"
                    "請改用不同的關鍵字或條件、換一個可用工具，或直接根據已有資訊給出 Final Answer。"
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
                seen_action_keys.add(action_key)

            this_action_failed = _looks_like_no_result(observation)
            if action == last_action and last_action_failed and this_action_failed:
                observation += (
                    f"\n\n系統提示：你已經呼叫過「{action}」都查無資料，"
                    "請不要再重複呼叫同一個工具（即使關鍵字寫法不同），"
                    "請改用其他可用工具查詢，或直接依現有資訊給出 Final Answer 並誠實告知查不到。"
                )
            last_action = action
            last_action_failed = this_action_failed

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
            "step": step_limit,
        }
    finally:
        await stack.aclose()
