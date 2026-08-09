import asyncio


async def web_search(query: str) -> str:
    """Search the public web via DuckDuckGo and return a short, readable summary."""
    try:
        from ddgs import DDGS
    except ImportError:
        return "[web_search 工具錯誤] 缺少 ddgs 套件，請執行 pip install ddgs"

    try:
        items = await asyncio.to_thread(
            lambda: DDGS().text(query, region="tw-tzh", max_results=5)
        )
    except Exception as exc:  # noqa: BLE001 - surface as tool observation, not a crash
        return f"[web_search 工具錯誤] {exc}"

    if not items:
        return f"沒有找到與「{query}」相關的網路搜尋結果。"

    lines = [f"網路搜尋「{query}」的結果："]
    for i, item in enumerate(items, start=1):
        title = item.get("title", "(無標題)")
        url = item.get("href", "")
        content = (item.get("body") or "").strip().replace("\n", " ")
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{i}. {title} ({url})\n   {content}")
    return "\n".join(lines)
