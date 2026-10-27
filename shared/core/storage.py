"""存储操作表 —— 根据配置决定文件存放位置和命名。"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from re import sub

from .constants import VOLUME

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


def detect_extension(work: dict, profile_key: str = "") -> str:
    """根据作品数据和输出配置判断扩展名。"""
    from shared.core.formats import OUTPUT_PROFILES, ContainerFormat
    if profile_key and profile_key in OUTPUT_PROFILES:
        prof = OUTPUT_PROFILES[profile_key]
        if prof.container == ContainerFormat.RAW:
            pass
        else:
            return prof.container.value
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


class _DedupIndex:
    """下载记录索引 —— 内存 set 缓存, 避免每次全量读文件。"""

    def __init__(self, record_file):
        self.file = record_file
        self._ids = None

    def _load(self):
        if self._ids is None:
            ids = set()
            if self.file.exists():
                try:
                    ids = set(self.file.read_text(encoding="utf-8").splitlines())
                except OSError:
                    ids = set()
            self._ids = ids
        return self._ids

    def has(self, work_id: str) -> bool:
        return work_id in self._load()

    def add(self, work_id: str) -> None:
        ids = self._load()
        if work_id in ids:
            return
        ids.add(work_id)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(work_id + "\n")


class StorageOps:
    """存储操作表。"""

    def __init__(self, platform: str, config: StorageConfig):
        self.platform = platform
        self.config = config
        # 使用 constants.VOLUME (正确处理 PyInstaller frozen 路径)
        self.base_dir = VOLUME / platform
        record = self.base_dir / ".downloaded_ids.txt"
        self._dedup = _DedupIndex(record)

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

    async def save_data(self, data: list[dict], name: str):
        if not data:
            return None
        self.base_dir.mkdir(parents=True, exist_ok=True)
        match self.config.data_format:
            case "csv":
                return await self._save_csv(data, self.base_dir / f"{name}.csv")
            case "json" | _:
                return await self._save_json(data, self.base_dir / f"{name}.json")

    def is_downloaded(self, work_id: str) -> bool:
        if not self.config.dedup:
            return False
        return self._dedup.has(work_id)

    def record_download(self, work_id: str):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._dedup.add(work_id)

    async def _save_json(self, data: list[dict], path: Path) -> str:
        import aiofiles
        from json import dumps
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(dumps(data, ensure_ascii=False, indent=2))
        return str(path)

    async def _save_csv(self, data: list[dict], path: Path) -> str:
        """CSV 保存 —— 标准库 csv 模块, 正确处理逗号/引号/换行。"""
        import aiofiles
        if not data:
            return str(path)
        buf = io.StringIO()
        fieldnames = list(data[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        async with aiofiles.open(path, "w", encoding="utf-8-sig", newline="") as f:
            await f.write(buf.getvalue())
        return str(path)
