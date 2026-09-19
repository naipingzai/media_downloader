"""Step 3: 数据提取 —— 解析JSON → 结构化数据。"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = ["DataExtractor", "WorkData"]


@dataclass
class WorkData:
    """统一的作品数据结构。"""
    platform: str
    work_id: str
    title: str = ""
    description: str = ""
    author_name: str = ""
    author_id: str = ""
    create_time: str = ""
    duration: int = 0
    width: int = 0
    height: int = 0
    video_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    music_url: str = ""
    cover_url: str = ""
    share_url: str = ""
    digg_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0
    play_count: int = 0
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "work_id": self.work_id,
            "title": self.title,
            "description": self.description,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "create_time": self.create_time,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "video_url": self.video_url,
            "image_urls": ",".join(self.image_urls),
            "music_url": self.music_url,
            "cover_url": self.cover_url,
            "share_url": self.share_url,
            "digg_count": self.digg_count,
            "comment_count": self.comment_count,
            "collect_count": self.collect_count,
            "share_count": self.share_count,
            "play_count": self.play_count,
        }


class DataExtractor:
    """统一的数据提取层。

    各平台适配器继承此类并实现:
    - extract_detail(): 解析单作品数据
    - extract_account(): 解析账号作品列表
    """

    def parse_timestamp(self, ts: int | str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """将时间戳转为格式化字符串。"""
        try:
            return datetime.fromtimestamp(int(ts)).strftime(fmt)
        except (ValueError, TypeError, OSError):
            return str(ts)

    def safe_get(self, data: dict, *keys, default=""):
        """安全地从嵌套字典取值。"""
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, default)
            else:
                return default
        return data or default
