"""国际化 — 支持中英文切换，配置文件持久化。"""
import json
from pathlib import Path
from shared.core.constants import VOLUME

CONFIG_FILE = VOLUME / "config.json"
_current_lang = "zh"

# ── 翻译表 ──
_TRANSLATIONS = {
    "zh": {
        # 平台名
        "douyin": "抖音",
        "kuaishou": "快手",
        "xiaohongshu": "小红书",
        "bilibili": "B站",
        # 主界面
        "app_name": "MediaDownloader",
        "subtitle": "多平台媒体下载",
        "download_console": "下载控制台",
        "download_console_desc": "支持抖音、快手、小红书、B站的媒体下载与采集工具",
        # 侧边栏
        "platforms": "平台选择",
        "settings": "设置",
        "open_download_dir": "打开下载目录",
        "login_cookie": "登录 / Cookie",
        # 面板标题
        "video_info": "作品资料卡",
        "feature_params": "功能与参数",
        "output_result": "输出结果",
        "exec_log": "执行日志",
        # 作品资料卡
        "waiting_parse": "等待解析",
        "parsed": "已解析",
        "parse_failed": "解析失败",
        "parse_hint": "输入链接后点击 解析预览 查看作品信息",
        # 功能参数
        "feature": "功能",
        "link": "链接",
        "options": "选项",
        "preview_parse": "解析预览",
        "execute": "执行",
        "link_placeholder": "粘贴链接/关键词",
        # 功能参数选项
        "danmaku": "弹幕",
        "subtitle_opt": "字幕",
        "cover": "封面",
        "metadata": "元数据",
        # 执行日志
        "executing": "执行 {feature}...",
        "parsing": "正在解析...",
        "parse_ok": "解析成功",
        "no_valid_link": "未提取到有效链接",
        "adapter_not_found": "平台适配器未找到",
        "input_url_hint": "请输入链接",
        "select_platform_hint": "请先选择平台",
        # 下载
        "downloading": "下载中...",
        "download_ok": "下载完成",
        "download_fail": "下载失败",
        "no_download_url": "无下载地址",
        "fetch_detail_fail": "获取详情失败",
        "parse_fail": "解析失败",
        "batch_download": "批量下载 {done}/{total} 个",
        "live_record": "直播录制",
        "merge_audio_video": "合并音视频...",
        "merge_fail": "合并失败",
        "ffmpeg_not_found": "FFmpeg未安装",
        # 设置
        "app_settings": "应用设置",
        "storage": "存储",
        "storage_mode": "存储模式:",
        "flat": "直接存储",
        "by_author": "按作者分目录",
        "by_date": "按日期分目录",
        "by_type": "按类型分目录",
        "data_format": "数据格式:",
        "json": "JSON",
        "csv": "CSV",
        "dedup": "去重:",
        "dedup_enable": "启用去重",
        "output_format": "输出格式",
        "video_profile": "视频预设:",
        "video_codec": "视频编码:",
        "audio_codec": "音频编码:",
        "image_format": "图片格式:",
        "download_options": "下载选项 (默认值)",
        "default_options": "默认选择:",
        "ffmpeg_section": "FFmpeg",
        "ffmpeg_path": "路径:",
        "ffmpeg_browse": "浏览...",
        "save": "保存",
        "cancel": "取消",
        # 登录
        "login_title": "{platform} 登录",
        "current_status": "当前状态: {status} ({count}字符)",
        "status_set": "已设置",
        "status_unset": "未设置",
        "qr_scan_hint": "使用 {platform} App 扫描二维码登录",
        "click_to_generate": "点击下方按钮生成二维码",
        "generate_qr": "生成二维码",
        "refresh": "刷新",
        "qr_scanning": "请用 {platform} App 扫描二维码",
        "qr_scanned": "已扫码,等待确认...",
        "qr_expired": "二维码已过期,请刷新",
        "qr_success": "登录成功!",
        "cookie_input_hint": "从浏览器 DevTools > Application > Cookies 复制",
        "save_cookie": "保存 Cookie",
        "clear": "清除",
        "cookie_saved": "Cookie 已保存",
        "cookie_empty_warn": "请输入 Cookie",
        # 采集
        "hot_list": "抖音热榜 TOP 20",
        "comment_data": "评论数据",
        "search_result": "搜索结果",
        "account_info": "账号资料",
        # 通用
        "yes": "是",
        "no": "否",
        "ok": "确定",
        "error": "错误",
        "version": "版本 {version}",
        "rank": "排名",
        "keyword": "关键词",
        "hot_value": "热度",
        "user": "用户",
        "content": "内容",
        "likes": "点赞",
        "title_field": "标题",
        "author": "作者",
        "nickname": "昵称",
        "followers": "粉丝",
        "following": "关注",
        "works": "作品数",
        "signature": "签名",
        # 输出结果
        "no_data": "暂无数据",
        "status_col": "状态",
        "source_col": "来源",
        "path_col": "路径",
        # 任务队列
        "task_queue": "任务队列",
        "pause_all": "全部暂停",
        "resume_all": "全部继续",
        "clear_done": "清除完成",
        # Hero
        "select_platform_start": "选择平台开始",
        "features_available": "{count} 个功能可用",
    },
    "en": {
        # Platform names
        "douyin": "Douyin",
        "kuaishou": "Kuaishou",
        "xiaohongshu": "Xiaohongshu",
        "bilibili": "Bilibili",
        # Main
        "app_name": "MediaDownloader",
        "subtitle": "Multi-platform Media Downloader",
        "download_console": "Download Console",
        "download_console_desc": "Media download & collection tool for Douyin, Kuaishou, Xiaohongshu, Bilibili",
        # Sidebar
        "platforms": "Platforms",
        "settings": "Settings",
        "open_download_dir": "Open Download Dir",
        "login_cookie": "Login / Cookie",
        # Panels
        "video_info": "Video Info",
        "feature_params": "Features & Params",
        "output_result": "Output",
        "exec_log": "Execution Log",
        # Video info
        "waiting_parse": "Waiting",
        "parsed": "Parsed",
        "parse_failed": "Parse Failed",
        "parse_hint": "Paste a link and click Preview to view info",
        # Feature panel
        "feature": "Feature",
        "link": "Link",
        "options": "Options",
        "preview_parse": "Preview",
        "execute": "Execute",
        "link_placeholder": "Paste link / keyword",
        # Options
        "danmaku": "Danmaku",
        "subtitle_opt": "Subtitle",
        "cover": "Cover",
        "metadata": "Metadata",
        # Log
        "executing": "Running {feature}...",
        "parsing": "Parsing...",
        "parse_ok": "Parse OK",
        "no_valid_link": "No valid link found",
        "adapter_not_found": "Platform adapter not found",
        "input_url_hint": "Please enter a URL",
        "select_platform_hint": "Please select a platform first",
        # Download
        "downloading": "Downloading...",
        "download_ok": "Download complete",
        "download_fail": "Download failed",
        "no_download_url": "No download URL",
        "fetch_detail_fail": "Failed to fetch detail",
        "parse_fail": "Parse failed",
        "batch_download": "Batch download {done}/{total}",
        "live_record": "Live Record",
        "merge_audio_video": "Merging audio & video...",
        "merge_fail": "Merge failed",
        "ffmpeg_not_found": "FFmpeg not installed",
        # Settings
        "app_settings": "Settings",
        "storage": "Storage",
        "storage_mode": "Storage Mode:",
        "flat": "Flat",
        "by_author": "By Author",
        "by_date": "By Date",
        "by_type": "By Type",
        "data_format": "Data Format:",
        "json": "JSON",
        "csv": "CSV",
        "dedup": "Dedup:",
        "dedup_enable": "Enable Dedup",
        "output_format": "Output Format",
        "video_profile": "Video Profile:",
        "video_codec": "Video Codec:",
        "audio_codec": "Audio Codec:",
        "image_format": "Image Format:",
        "download_options": "Download Options (Defaults)",
        "default_options": "Default:",
        "ffmpeg_section": "FFmpeg",
        "ffmpeg_path": "Path:",
        "ffmpeg_browse": "Browse...",
        "save": "Save",
        "cancel": "Cancel",
        # Login
        "login_title": "{platform} Login",
        "current_status": "Status: {status} ({count} chars)",
        "status_set": "Set",
        "status_unset": "Not Set",
        "qr_scan_hint": "Scan QR code with {platform} App",
        "click_to_generate": "Click button below to generate QR code",
        "generate_qr": "Generate QR Code",
        "refresh": "Refresh",
        "qr_scanning": "Please scan with {platform} App",
        "qr_scanned": "Scanned, waiting for confirm...",
        "qr_expired": "QR expired, please refresh",
        "qr_success": "Login success!",
        "cookie_input_hint": "Copy from browser DevTools > Application > Cookies",
        "save_cookie": "Save Cookie",
        "clear": "Clear",
        "cookie_saved": "Cookie saved",
        "cookie_empty_warn": "Please enter Cookie",
        # Collect
        "hot_list": "Douyin Hot List TOP 20",
        "comment_data": "Comments",
        "search_result": "Search Results",
        "account_info": "Account Info",
        # Common
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "error": "Error",
        "version": "Version {version}",
        "rank": "Rank",
        "keyword": "Keyword",
        "hot_value": "Hot",
        "user": "User",
        "content": "Content",
        "likes": "Likes",
        "title_field": "Title",
        "author": "Author",
        "nickname": "Nickname",
        "followers": "Followers",
        "following": "Following",
        "works": "Works",
        "signature": "Bio",
        # Output
        "no_data": "No Data",
        "status_col": "Status",
        "source_col": "Source",
        "path_col": "Path",
        # Task
        "task_queue": "Task Queue",
        "pause_all": "Pause All",
        "resume_all": "Resume All",
        "clear_done": "Clear Done",
        # Hero
        "select_platform_start": "Select a platform to start",
        "features_available": "{count} features available",
    },
}


def t(key: str, **kwargs) -> str:
    """获取翻译文本，支持 {key} 模板替换。"""
    text = _TRANSLATIONS.get(_current_lang, {}).get(key,
           _TRANSLATIONS.get("zh", {}).get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text


def get_lang() -> str:
    return _current_lang


def set_lang(lang: str):
    global _current_lang
    if lang in _TRANSLATIONS:
        _current_lang = lang
        _save_lang(lang)


def _save_lang(lang: str):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["language"] = lang
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_lang():
    global _current_lang
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _current_lang = data.get("language", "zh")
        except Exception:
            pass


def platform_name(pid: str) -> str:
    """获取平台中文名。"""
    return t(pid)
