"""存储操作表 —— 根据配置决定文件存放位置和命名。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from re import sub

__all__ = ["StorageOps", "StorageConfig"]


@dataclass
class StorageConfig:
    mode: str = "flat"
    data_format: str = "json"
    dedup: bool = True


def safe_name(text: str) -> str:
    """过滤非法文件名字符。"""
    text = sub(r'[\\/:*?"<>|\r\n]', '', text)
    return text.strip()[:80] or "unknown"


def detect_extension(work: dict) -> str:
    """根据作品数据判断扩展名。"""
    if work.get("video_url"):
        return "mp4"
    if work.get("image_urls"):
        return "jpg"
    return "mp4"


def format_date(timestamp: int) -> str:
    """时间戳转日期字符串。"""
    if timestamp > 1e12:
        timestamp = timestamp // 1000
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    except Exception:
        return "unknown-date"


class StorageOps:
    """存储操作表。"""

    def __init__(self, platform: str, config: StorageConfig):
        self.platform = platform
        self.config = config
        self.base_dir = Path(__file__).resolve().parent.parent.parent / "Volume" / platform

    def resolve_dir(self, work: dict) -> Path:
        match self.config.mode:
            case "flat":
                return self.base_dir
            case "by_author":
                return self.base_dir / safe_name(work.get("author_name", "unknown"))
            case "by_date":
                return self.base_dir / format_date(work.get("create_time", 0))
            case "by_type":
                return self.base_dir / ("video" if work.get("video_url") else "image")
            case _:
                return self.base_dir

    def resolve_filename(self, work: dict) -> str:
        author = safe_name(work.get("author_name", "unknown"))
        desc = safe_name(work.get("title", "untitled"))
        ext = detect_extension(work)
        return f"{author}_{desc}.{ext}"

    def resolve(self, work: dict) -> Path:
        target_dir = self.resolve_dir(work)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / self.resolve_filename(work)

    async def save_data(self, data: list[dict], name: str) -> str | None:
        if not data:
            return None
        self.base_dir.mkdir(parents=True, exist_ok=True)
        match self.config.data_format:
            case "csv":
                return await self._save_csv(data, self.base_dir / f"{name}.csv")
            case "json":
                return await self._save_json(data, self.base_dir / f"{name}.json")
            case _:
                return await self._save_json(data, self.base_dir / f"{name}.json")

    def is_downloaded(self, work_id: str) -> bool:
        if not self.config.dedup:
            return False
        record = self.base_dir / ".downloaded_ids.txt"
        if not record.exists():
            return False
        return work_id in record.read_text().splitlines()

    def record_download(self, work_id: str):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        record = self.base_dir / ".downloaded_ids.txt"
        with open(record, "a") as f:
            f.write(work_id + "\n")

    async def _save_json(self, data: list[dict], path: Path) -> str:
        import aiofiles
        from json import dumps
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(dumps(data, ensure_ascii=False, indent=2))
        return str(path)

    async def _save_csv(self, data: list[dict], path: Path) -> str:
        import aiofiles, csv
        async with aiofiles.open(path, "w", encoding="utf-8-sig", newline="") as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                await f.write(",".join(data[0].keys()) + "\n")
                for row in data:
                    await f.write(",".join(str(v) for v in row.values()) + "\n")
        return str(path)
