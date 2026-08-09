"""Seed the database with sample GIGABYTE motherboard products + RAG documents.

Run after `init_db.sql` has been applied:

    python scripts/seed_data.py

Requires a local Ollama instance running with the embedding model pulled
(`ollama pull nomic-embed-text`), since RAG documents are embedded here.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.llm import embed  # noqa: E402
from app.db.database import AsyncSessionLocal  # noqa: E402
from app.db.models import KBDocument, Motherboard  # noqa: E402

MOTHERBOARDS = [
    dict(
        model_name="B650 AORUS ELITE AX",
        series="AORUS",
        socket="AM5",
        chipset="B650",
        form_factor="ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 4.0",
        m2_slots=3,
        wifi=True,
        price_twd=6490,
        release_date=date(2022, 9, 27),
        description=(
            "B650 AORUS ELITE AX 是主打 AMD Ryzen 7000 系列處理器的中階 ATX 主機板，"
            "支援 DDR5 記憶體與 PCIe 4.0 x16 顯示卡插槽，內建 Wi-Fi 6E 與 2.5GbE 網路，"
            "適合一般文書、遊戲玩家的主流選擇。"
        ),
        extra_specs={"lan": "2.5GbE", "usb_c": True, "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="X670E AORUS MASTER",
        series="AORUS",
        socket="AM5",
        chipset="X670E",
        form_factor="E-ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 5.0",
        m2_slots=5,
        wifi=True,
        price_twd=14990,
        release_date=date(2022, 9, 27),
        description=(
            "X670E AORUS MASTER 為技嘉 AM5 平台的旗艦級主機板，供電規格達 18+2+2 相，"
            "全面支援 PCIe 5.0 顯示卡與 M.2 SSD，內建 Wi-Fi 6E、10GbE 網路，"
            "適合高階玩家與內容創作者的極致效能需求。"
        ),
        extra_specs={"lan": "10GbE", "vrm_phases": "18+2+2", "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="B650M AORUS ELITE",
        series="AORUS",
        socket="AM5",
        chipset="B650",
        form_factor="Micro-ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 4.0",
        m2_slots=2,
        wifi=False,
        price_twd=5290,
        release_date=date(2022, 10, 15),
        description=(
            "B650M AORUS ELITE 是 Micro-ATX 規格的入門級 AM5 主機板，體積精巧適合小機殼組裝，"
            "提供基本 DDR5 支援與 PCIe 4.0，性價比高，適合預算有限的玩家。"
        ),
        extra_specs={"lan": "1GbE", "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="Z790 AORUS ELITE AX",
        series="AORUS",
        socket="LGA1700",
        chipset="Z790",
        form_factor="ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 5.0",
        m2_slots=4,
        wifi=True,
        price_twd=8490,
        release_date=date(2022, 10, 20),
        description=(
            "Z790 AORUS ELITE AX 支援 Intel 第 13/14 代 Core 處理器，具備 PCIe 5.0 顯卡插槽、"
            "4 組 M.2 SSD 插槽與 Wi-Fi 6E，是中高階玩家兼顧效能與擴充性的熱門選擇。"
        ),
        extra_specs={"lan": "2.5GbE", "usb_c": True, "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="Z790 AORUS MASTER",
        series="AORUS",
        socket="LGA1700",
        chipset="Z790",
        form_factor="E-ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 5.0",
        m2_slots=5,
        wifi=True,
        price_twd=15990,
        release_date=date(2022, 10, 20),
        description=(
            "Z790 AORUS MASTER 為 LGA1700 平台旗艦主機板，20+1+2 相供電設計搭配 直觸式散熱模組，"
            "支援 Intel 第 13/14 代處理器超頻，內建 Wi-Fi 6E 與 10GbE 網路，"
            "適合極限超頻玩家與高階創作工作站需求。"
        ),
        extra_specs={"lan": "10GbE", "vrm_phases": "20+1+2", "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="B760M AORUS ELITE AX",
        series="AORUS",
        socket="LGA1700",
        chipset="B760",
        form_factor="Micro-ATX",
        memory_type="DDR5",
        memory_slots=4,
        max_memory_gb=128,
        pcie_version="PCIe 4.0",
        m2_slots=3,
        wifi=True,
        price_twd=5990,
        release_date=date(2023, 1, 3),
        description=(
            "B760M AORUS ELITE AX 是 Micro-ATX 規格的主流級 LGA1700 主機板，支援 DDR5 記憶體，"
            "內建 Wi-Fi 6E，提供三組 M.2 SSD 插槽，適合搭配 Intel i5/i7 處理器的主流遊戲玩家。"
        ),
        extra_specs={"lan": "2.5GbE", "rgb": "RGB Fusion 2.0"},
    ),
    dict(
        model_name="A620M AORUS ELITE",
        series="AORUS",
        socket="AM5",
        chipset="A620",
        form_factor="Micro-ATX",
        memory_type="DDR5",
        memory_slots=2,
        max_memory_gb=64,
        pcie_version="PCIe 3.0",
        m2_slots=2,
        wifi=False,
        price_twd=3290,
        release_date=date(2023, 6, 1),
        description=(
            "A620M AORUS ELITE 是最入門的 AM5 平台主機板，不支援 CPU 超頻，"
            "適合預算導向、只需穩定文書與輕度遊戲效能的使用者，是進入 AM5 平台最便宜的選擇。"
        ),
        extra_specs={"lan": "1GbE", "overclock_supported": False},
    ),
    dict(
        model_name="TRX50 AERO D",
        series="AERO",
        socket="sTR5",
        chipset="TRX50",
        form_factor="E-ATX",
        memory_type="DDR5",
        memory_slots=8,
        max_memory_gb=2048,
        pcie_version="PCIe 5.0",
        m2_slots=5,
        wifi=True,
        price_twd=24990,
        release_date=date(2023, 11, 21),
        description=(
            "TRX50 AERO D 針對 AMD Ryzen Threadripper 7000 系列 HEDT 平台設計，"
            "白色外觀搭配創作者導向的散熱與擴充配置，支援 8 通道 DDR5 記憶體，最高可達 2TB 容量，"
            "適合 3D 渲染、影片剪輯等專業工作站應用。"
        ),
        extra_specs={"lan": "10GbE", "target": "workstation/creator"},
    ),
]


async def seed():
    async with AsyncSessionLocal() as session:
        for mb_data in MOTHERBOARDS:
            existing = await session.scalar(
                select(Motherboard).where(Motherboard.model_name == mb_data["model_name"])
            )
            if existing:
                print(f"[skip] {mb_data['model_name']} 已存在")
                continue

            mb = Motherboard(**mb_data)
            session.add(mb)
            await session.flush()  # get mb.id

            # Build a RAG document (rich text chunk) per motherboard and embed it.
            doc_text = (
                f"產品型號：{mb.model_name}\n"
                f"系列：{mb.series}\n"
                f"CPU 腳位：{mb.socket}\n"
                f"晶片組：{mb.chipset}\n"
                f"板型：{mb.form_factor}\n"
                f"記憶體：{mb.memory_type}，{mb.memory_slots} 插槽，最高支援 {mb.max_memory_gb}GB\n"
                f"PCIe 版本：{mb.pcie_version}\n"
                f"M.2 插槽數：{mb.m2_slots}\n"
                f"內建 Wi-Fi：{'是' if mb.wifi else '否'}\n"
                f"建議售價：NT${mb.price_twd}\n"
                f"上市日期：{mb.release_date}\n"
                f"說明：{mb.description}\n"
            )
            vector = await embed(doc_text)
            doc = KBDocument(
                motherboard_id=mb.id,
                title=f"{mb.model_name} 產品規格",
                content=doc_text,
                embedding=vector,
                doc_metadata={"model_name": mb.model_name, "series": mb.series},
            )
            session.add(doc)
            print(f"[add] {mb.model_name}")

        await session.commit()
    print("Seed 完成。")


if __name__ == "__main__":
    asyncio.run(seed())
