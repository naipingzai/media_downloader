"""Step 5: 数据存储 —— 持久化 + 记录管理。"""
from __future__ import annotations
from pathlib import Path
from typing import Any

__all__ = ["DataStorage"]


class DataStorage:
    """统一的数据存储层。

    支持: CSV / XLSX / SQLite / JSON
    管理: 已下载作品ID记录 → 防重复下载
    """

    def __init__(self, save_dir: Path, storage_format: str = ""):
        self.save_dir = save_dir
        self.format = storage_format
        self.save_dir.mkdir(parents=True, exist_ok=True)

    async def save_works(self, works: list[dict], filename: str = "works") -> str | None:
        """保存作品数据。"""
        if not self.format or not works:
            return None
        match self.format:
            case "csv":
                return await self._save_csv(works, filename)
            case "xlsx":
                return self._save_xlsx(works, filename)
            case "sql":
                return await self._save_sql(works, filename)
            case "json":
                return await self._save_json(works, filename)
        return None

    def is_downloaded(self, work_id: str) -> bool:
        """检查作品是否已下载。"""
        record_file = self.save_dir / ".downloaded_ids.txt"
        if not record_file.exists():
            return False
        return work_id in record_file.read_text().splitlines()

    def record_download(self, work_id: str):
        """记录已下载的作品ID。"""
        record_file = self.save_dir / ".downloaded_ids.txt"
        with open(record_file, "a") as f:
            f.write(work_id + "\n")

    async def _save_csv(self, data: list[dict], name: str) -> str:
        import csv, aiofiles
        path = self.save_dir / f"{name}.csv"
        async with aiofiles.open(path, "w", encoding="utf-8-sig", newline="") as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                await f.write(",".join(data[0].keys()) + "\n")
                for row in data:
                    await f.write(",".join(str(v) for v in row.values()) + "\n")
        return str(path)

    def _save_xlsx(self, data: list[dict], name: str) -> str:
        from openpyxl import Workbook
        path = self.save_dir / f"{name}.xlsx"
        wb = Workbook()
        ws = wb.active
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        wb.save(path)
        return str(path)

    async def _save_sql(self, data: list[dict], name: str) -> str:
        import aiosqlite
        path = self.save_dir / f"{name}.db"
        async with aiosqlite.connect(path) as db:
            if data:
                cols = ", ".join(data[0].keys())
                ph = ", ".join(["?"] * len(data[0]))
                await db.execute(f"CREATE TABLE IF NOT EXISTS works ({cols})")
                for row in data:
                    await db.execute(f"INSERT OR REPLACE INTO works VALUES ({ph})", list(row.values()))
                await db.commit()
        return str(path)

    async def _save_json(self, data: list[dict], name: str) -> str:
        from json import dumps
        import aiofiles
        path = self.save_dir / f"{name}.json"
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(dumps(data, ensure_ascii=False, indent=2))
        return str(path)
