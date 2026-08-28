"""Generic database admin endpoints: list every table registered on the app's
declarative Base, browse a table's rows, and delete a single row by its
primary key. Used by the small "資料庫管理" button in the UI so the user can
inspect/clean up any table without opening a DB client.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Table, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Base

router = APIRouter(prefix="/api/admin/db", tags=["admin"])

_TABLES: dict[str, Table] = {table.name: table for table in Base.metadata.sorted_tables}


def _get_table(table_name: str) -> Table:
    table = _TABLES.get(table_name)
    if table is None:
        raise HTTPException(status_code=404, detail=f"資料表不存在：{table_name}")
    return table


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, dict)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        length = len(value)
    except TypeError:
        return str(value)
    return list(value) if length <= 20 else f"[{length} 個元素]"


@router.get("/tables")
async def list_tables(session: AsyncSession = Depends(get_session)):
    tables = []
    for name, table in _TABLES.items():
        total = (await session.execute(select(func.count()).select_from(table))).scalar_one()
        tables.append(
            {
                "name": name,
                "columns": [c.name for c in table.columns],
                "primary_key": [c.name for c in table.primary_key.columns],
                "row_count": total,
            }
        )
    return tables


@router.get("/tables/{table_name}/rows")
async def list_rows(
    table_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    table = _get_table(table_name)
    pk_cols = list(table.primary_key.columns)
    order_col = pk_cols[0] if pk_cols else list(table.columns)[0]
    stmt = select(table).order_by(order_col.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()
    total = (await session.execute(select(func.count()).select_from(table))).scalar_one()
    return {
        "columns": [c.name for c in table.columns],
        "primary_key": [c.name for c in pk_cols],
        "total": total,
        "rows": [{c.name: _serialize(getattr(row, c.name)) for c in table.columns} for row in rows],
    }


@router.delete("/tables/{table_name}/rows/{pk_value}")
async def delete_row(table_name: str, pk_value: str, session: AsyncSession = Depends(get_session)):
    table = _get_table(table_name)
    pk_cols = list(table.primary_key.columns)
    if len(pk_cols) != 1:
        raise HTTPException(status_code=400, detail="僅支援單一主鍵欄位的資料表")

    pk_col = pk_cols[0]
    try:
        typed_value: Any = pk_col.type.python_type(pk_value)
    except (ValueError, NotImplementedError):
        typed_value = pk_value

    stmt = table.delete().where(pk_col == typed_value)
    try:
        result = await session.execute(stmt)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"刪除失敗，其他資料表仍參照此筆資料：{exc.orig}") from exc

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="找不到該筆資料")
    return {"status": "deleted"}
