"""下载记录 —— GUI / TUI 共用的全局下载历史。

存储: Volume/history.jsonl (一行一条 JSON), 追加写 + 崩溃安全。
字段: 平台/作品ID/标题(作品介绍)/作者/作者主页/作品链接/发布日期/
      下载时间/保存路径/下载日志。
查询: 倒序读取 (最新在前), 供 UI 表格展示。
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from .constants import VOLUME

__all__ = ["DownloadHistory", "get_history"]

_LOCK = threading.Lock()
_HISTORY_FILE = VOLUME / "history.jsonl"


class DownloadHistory:
    """全局下载记录 (JSON Lines, 线程安全, GUI/TUI 共用)。"""

    FIELDS = (
        "platform", "work_id", "title", "author_name", "author_home",
        "share_url", "publish_date", "downloaded_at", "file_path", "log",
    )

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else _HISTORY_FILE

    # ---------- 写入 ----------

    def add(self, *, platform: str, work_id: str, title: str = "",
            author_name: str = "", author_home: str = "",
            share_url: str = "", publish_date: str = "",
            file_path: str = "", log: list[str] | None = None) -> dict:
        """追加一条下载记录, 返回完整记录 dict。"""
        rec = {
            "platform": platform or "",
            "work_id": str(work_id or ""),
            "title": (title or "").strip(),
            "author_name": author_name or "",
            "author_home": author_home or "",
            "share_url": share_url or "",
            "publish_date": publish_date or "",
            "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": file_path or "",
            "log": [str(x) for x in (log or [])][-50:],  # 日志上限 50 行
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        from json import dumps
        with _LOCK:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(dumps(rec, ensure_ascii=False) + "\n")
        return rec

    # ---------- 读取 ----------

    def load(self, limit: int = 500) -> list[dict]:
        """读取记录 (最新在前)。"""
        if not self.path.exists():
            return []
        from json import loads
        rows: list[dict] = []
        with _LOCK:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return []
        for line in reversed(lines):        # 最新在前
            line = line.strip()
            if not line:
                continue
            try:
                r = loads(line)
            except Exception:
                continue
            if isinstance(r, dict):
                rows.append(r)
            if len(rows) >= limit:
                break
        return rows

    def clear(self) -> None:
        """清空记录。"""
        with _LOCK:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass

    # ---------- 辅助 ----------

    @staticmethod
    def author_home_of(platform: str, author_id: str) -> str:
        """按平台拼接作者主页链接 (无 ID 时返回空)。"""
        aid = str(author_id or "").strip()
        if not aid:
            return ""
        return {
            "bilibili": f"https://space.bilibili.com/{aid}",
            "kuaishou": f"https://www.kuaishou.com/profile/{aid}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{aid}",
        }.get(platform, f"https://www.douyin.com/user/{aid}")

    @staticmethod
    def format_date(ts) -> str:
        """时间戳 (秒/毫秒) → 日期字符串; 无效返回空。"""
        try:
            ts = int(ts or 0)
        except (TypeError, ValueError):
            return ""
        if ts <= 0:
            return ""
        if ts > 1e12:
            ts //= 1000
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (OSError, OverflowError, ValueError):
            return ""


def get_history() -> DownloadHistory:
    """全局单例入口。"""
    global _instance
    try:
        return _instance            # type: ignore[name-defined]
    except NameError:
        _instance = DownloadHistory()
        return _instance
