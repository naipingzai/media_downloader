"""中文翻译表 —— UI 文本统一从这里获取。

仅保留简体中文一种语言。`t(key)` 直接返回中文文案, 可选 `**kwargs` 做模板替换。
"""
from __future__ import annotations

# ── 平台中文名 (短, 用于侧栏按钮/页签等) ──
PLATFORM_NAMES: dict[str, str] = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
}

# ── 翻译表 ──
_TRANSLATIONS: dict[str, str] = {
    # 通用
    "app_name": "MediaDownloader",
    "subtitle": "多平台媒体下载",
    "platforms": "平台",
    "tools": "工具",
    "account": "账号",
    "settings": "设置",
    "open_download_dir": "打开下载目录",
    "exec_log": "执行日志",
    "theme_dark": "暗色",
    "theme_light": "亮色",
    "font_size": "字号",
    "login_cookie": "登录 / Cookie",
    "version": "版本",

    # 功能区
    "link": "链接",
    "video_info": "作品资料",
    "author_info": "作者资料",
    "feature": "功能",
    "display_area": "展示区",

    # 主操作
    "preview_parse": "解析预览",
    "execute": "执行",
    "stop_recording": "停止录制",
    "copy_link": "获取链接",
    "show_comments": "查看评论",
    "download_cover": "下载封面",
    "fetch_works": "获取作品",
    "follow_list": "关注列表",
    "collect_list": "收藏列表",
    "download_avatar": "下载头像",
    "open_home": "获取主页",

    # 展示区页面
    "page_works": "作品列表",
    "page_works_batch": "批量下载预览",
    "page_following": "关注列表",
    "page_collection": "收藏列表",
    "page_comments": "评论列表",
    "page_hot": "热榜",
    "page_search": "搜索结果",
    "page_account": "账号资料",
    "page_login": "账号登录",
    "page_settings": "设置",

    # 提示
    "paste_link_placeholder": "粘贴作品链接 (抖音/快手/小红书/B站) → 点击解析预览",
    "select_platform_hint": "请先在左侧选择平台",
    "input_url_hint": "请先在链接栏粘贴链接",
    "no_data": "暂无数据",
    "loading": "加载中…",
    "ready": "就绪",
    "close_page": "关闭",
    "close_all_pages": "关闭全部",
    "cancel": "取消",
    "save": "保存",
    "clear": "清除",
    "refresh": "刷新",
    "ok": "确定",

    # 状态
    "login_success": "登录成功!",
    "cookie_saved": "Cookie 已保存",
    "cookie_empty_warn": "请先粘贴 Cookie 内容",
    "saved_to_clipboard": "已复制到剪贴板",

    # 设置分组
    "card_storage": "存储",
    "card_output": "输出格式",
    "card_download": "下载选项",
    "card_ffmpeg": "FFmpeg",
    "card_appearance": "外观",
    "storage_mode": "存储模式:",
    "data_format": "数据格式:",
    "dedup": "去重:",
    "video_profile": "视频预设:",
    "video_codec": "视频编码:",
    "audio_codec": "音频编码:",
    "image_format": "图片格式:",
    "default_options": "默认下载选项:",
    "ffmpeg_path": "FFmpeg 路径:",
    "ffmpeg_browse": "浏览…",
    "ffmpeg_status_ok": "FFmpeg 可用",
    "ffmpeg_status_fail": "FFmpeg 不可用",

    # 设置项
    "mode_flat": "直接存储",
    "mode_by_author": "按作者分目录",
    "mode_by_date": "按日期分目录",
    "mode_by_type": "按类型分目录",
    "format_json": "JSON",
    "format_csv": "CSV",
    "opt_danmaku": "弹幕",
    "opt_subtitle": "字幕",
    "opt_cover": "封面",
    "opt_metadata": "元数据",
    "dedup_enable": "启用去重",
    "font_size_hint": "调整界面字号 (12~20)",
}


def t(key: str, **kwargs) -> str:
    """获取中文文本, 支持 {key} 模板替换; key 不存在时回退到 key 本身。"""
    text = _TRANSLATIONS.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def platform_name(pid: str) -> str:
    """获取平台中文名 (找不到时返回 id 本身)。"""
    return PLATFORM_NAMES.get(pid, pid)
