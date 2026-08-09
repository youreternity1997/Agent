from sqlalchemy import or_, select

from app.db.database import AsyncSessionLocal
from app.db.models import Motherboard


async def db_query(keyword: str, limit: int = 5) -> str:
    """Exact/structured lookup against the motherboards table (by model name, series, socket or chipset)."""
    pattern = f"%{keyword.strip()}%"
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Motherboard)
            .where(
                or_(
                    Motherboard.model_name.ilike(pattern),
                    Motherboard.series.ilike(pattern),
                    Motherboard.socket.ilike(pattern),
                    Motherboard.chipset.ilike(pattern),
                )
            )
            .limit(limit)
        )
        try:
            rows = (await session.execute(stmt)).scalars().all()
        except Exception as exc:  # noqa: BLE001
            return f"[db_query 工具錯誤] 資料庫查詢失敗：{exc}"

    if not rows:
        return f"資料庫中沒有找到符合「{keyword}」的主機板型號。"

    lines = [f"資料庫查詢「{keyword}」符合的主機板規格："]
    for mb in rows:
        lines.append(
            "- {name} | 系列:{series} | 腳位:{socket} | 晶片組:{chipset} | 板型:{ff} | "
            "記憶體:{mem_type} x{mem_slots} (最高{max_mem}GB) | {pcie} | M.2x{m2} | "
            "Wi-Fi:{wifi} | 售價:NT${price} | 上市:{rdate}".format(
                name=mb.model_name,
                series=mb.series,
                socket=mb.socket,
                chipset=mb.chipset,
                ff=mb.form_factor,
                mem_type=mb.memory_type,
                mem_slots=mb.memory_slots,
                max_mem=mb.max_memory_gb,
                pcie=mb.pcie_version,
                m2=mb.m2_slots,
                wifi="有" if mb.wifi else "無",
                price=mb.price_twd,
                rdate=mb.release_date,
            )
        )
    return "\n".join(lines)
