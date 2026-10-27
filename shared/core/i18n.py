"""平台中文名映射 —— UI 显示用。

历史说明: 本文件原为完整 i18n 翻译表 (t(key)), 但 UI 实际只使用
platform_name(); 翻译表已于 2026-10 清理。若未来需要多语言,
在此恢复 key-value 结构并重新导出 t() 即可。
"""
from __future__ import annotations

__all__ = ["PLATFORM_NAMES", "platform_name"]

PLATFORM_NAMES: dict[str, str] = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
}


def platform_name(pid: str) -> str:
    """获取平台中文名 (找不到时返回 id 本身)。"""
    return PLATFORM_NAMES.get(pid, pid)
