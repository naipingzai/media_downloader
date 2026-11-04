"""多语言 i18n —— 中文/English 运行时切换。

用法:
    from shared.core.i18n import t, set_lang, current_lang
    t("ui.download")            # → "下载" / "Download"
    set_lang("en")              # 切换语言 (UI 需自行刷新文本)

缺失 key: 回退中文 → 仍缺失则原样返回 key。
"""
from __future__ import annotations

LANGUAGES: dict[str, str] = {"zh": "中文", "en": "English"}

_cur = "zh"

# 平台显示名 (跟随语言; set_lang 时同步重建)
PLATFORM_NAMES: dict[str, str] = {
    "douyin": "抖音", "kuaishou": "快手",
    "xiaohongshu": "小红书", "bilibili": "B站",
}

__all__ = ["LANGUAGES", "PLATFORM_NAMES", "t", "set_lang",
           "current_lang", "platform_name"]

_STRINGS: dict[str, dict[str, str]] = {
    # ---------- 平台名 ----------
    "platform.douyin": {"zh": "抖音", "en": "Douyin"},
    "platform.kuaishou": {"zh": "快手", "en": "Kuaishou"},
    "platform.xiaohongshu": {"zh": "小红书", "en": "Xiaohongshu"},
    "platform.bilibili": {"zh": "B站", "en": "Bilibili"},
    # ---------- 通用 UI ----------
    "ui.download": {"zh": "下载", "en": "Download"},
    "ui.preview": {"zh": "解析预览", "en": "Preview"},
    "ui.settings": {"zh": "设置", "en": "Settings"},
    "ui.login": {"zh": "登录", "en": "Login"},
    "ui.close": {"zh": "关闭", "en": "Close"},
    "ui.save": {"zh": "保存", "en": "Save"},
    "ui.cancel": {"zh": "取消", "en": "Cancel"},
    "ui.select_all": {"zh": "全选", "en": "Select All"},
    "ui.select_none": {"zh": "全不选", "en": "Deselect All"},
    "ui.invert": {"zh": "反选", "en": "Invert"},
    "ui.load_more": {"zh": "加载更多", "en": "Load More"},
    "ui.download_selected": {"zh": "下载所选", "en": "Download Selected"},
    "ui.stop_all": {"zh": "全部停止", "en": "Stop All"},
    "ui.pause_all": {"zh": "暂停全部", "en": "Pause All"},
    "ui.resume_all": {"zh": "继续全部", "en": "Resume All"},
    "ui.tasks": {"zh": "下载任务", "en": "Tasks"},
    "ui.log": {"zh": "执行日志", "en": "Log"},
    "ui.history": {"zh": "下载记录", "en": "History"},
    "ui.features": {"zh": "功能", "en": "Features"},
    "ui.platform": {"zh": "平台", "en": "Platform"},
    "ui.author": {"zh": "作者资料", "en": "Author"},
    "ui.expand": {"zh": "查看完整资料", "en": "View Full Profile"},
    "ui.theme_dark": {"zh": "暗色", "en": "Dark"},
    "ui.theme_light": {"zh": "亮色", "en": "Light"},
    "ui.download_dir": {"zh": "下载目录", "en": "Download Dir"},
}


def t(key: str, **kwargs) -> str:
    """取翻译: 当前语言 → 中文回退 → key 本身。"""
    entry = _STRINGS.get(key)
    if entry:
        s = entry.get(_cur) or entry.get("zh") or key
        return s.format(**kwargs) if kwargs else s
    return key


def set_lang(lang: str):
    """切换语言 (zh/en), 平台名跟随更新。"""
    global _cur
    if lang in LANGUAGES:
        _cur = lang
    PLATFORM_NAMES.clear()
    for pid in ("douyin", "kuaishou", "xiaohongshu", "bilibili"):
        PLATFORM_NAMES[pid] = t(f"platform.{pid}")


def current_lang() -> str:
    """当前语言代码 (zh/en)。"""
    return _cur


def platform_name(pid: str) -> str:
    """平台显示名 (跟随当前语言; 找不到返回 id 本身)。"""
    return PLATFORM_NAMES.get(pid) or pid
