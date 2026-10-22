"""TUI 主应用 — 布局与 GUI (ui/gui/main_window.py) 一一对应。

┌─────────────────────────────────────────────────────────────┐
│ Header: 品牌 · 平台切换 · [登录] [设置] [数据] [退出]          │
├──────────────────────────┬──────────────────────────────────┤
│ ┌ 作者资料 (Static) ────┐ │ ┌ 链接 (Input + 解析预览) ─────┐ │
│ │ 昵称/签名/粉丝/关注    │ │ ├ 功能 (作品/作者/平台按钮) ───┤ │
│ ├───────────────────────┤ │ │  (随平台 FeatureMeta 动态)   │ │
│ │ 作品资料 (Static)     │ │ ├ 执行日志 (RichLog) ─────────┤ │
│ │ 标题/作者/时长/统计    │ │ │  实时滚动                    │ │
│ └───────────────────────┘ │ └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Footer 状态栏: Cookie 状态 | FFmpeg | 版本                    │
└─────────────────────────────────────────────────────────────┘
模态屏 (对应 GUI ToolWindow):
  LoginScreen / SettingsScreen / BatchSelectScreen / DataTableScreen
"""
from __future__ import annotations

import asyncio
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, RichLog,
)

from shared.core import (
    PROJECT_NAME, VOLUME, CookieManager, PlatformBus,
    platform_name as _pn, FFmpegManager, ConfigManager,
)
from platforms import load_all_platforms

APP_VERSION_LABEL = "MediaDownloader TUI V1.0"

# 日志颜色映射 (对应 GUI LogPanel 的颜色语义)
_LOG_COLORS = {
    "✓": "green",
    "✗": "red",
    "⚠": "yellow",
    "▸": "cyan",
}


def _color_of(msg: str) -> str:
    for k, v in _LOG_COLORS.items():
        if msg.startswith(k):
            return v
    return ""


# ===================== 模态屏: 登录 (对应 LoginPage) =====================

class LoginScreen(ModalScreen):
    """登录屏 — QR 码 (终端字符画) + Cookie 手动粘贴。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    LoginScreen { align: center middle; }
    #login-dlg { width: 64; height: auto; max-height: 90%; border: round $primary;
                 background: $surface; padding: 1 2; }
    #login-title { text-style: bold; color: $text; }
    #qr-box { width: auto; height: auto; align-horizontal: center;
              background: white; padding: 0; }
    #qr-art { color: black on white; }
    #login-status { color: $warning; height: auto; }
    #login-actions { height: auto; align-horizontal: right; }
    """

    def __init__(self, platform: str, cookie_hint: str = ""):
        super().__init__()
        self.platform = platform
        self.cookie_hint = cookie_hint
        self._cm = CookieManager()
        self._qr_key = ""
        self._manager = None
        self._poll_count = 0

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll

        with Vertical(id="login-dlg"):
            yield Label(f"登录 · {_pn(self.platform)}", id="login-title")
            cur = self._cm.get(self.platform)
            if cur:
                yield Label(f"● 已配置 Cookie ({len(cur)} 字符)",
                            id="login-status")
            else:
                yield Label("● 未配置 Cookie", id="login-status")
            with VerticalScroll():
                from shared.core import LoginBus
                if LoginBus.has_qr(self.platform):
                    yield Label("扫码登录 — 使用 App 扫描下方二维码")
                    with Vertical(id="qr-box"):
                        yield Label("点击[生成二维码]", id="qr-art")
                    yield Button("生成二维码", id="btn-gen-qr", variant="primary")
                if self.cookie_hint:
                    yield Label(f"建议 Cookie 包含: {self.cookie_hint}")
                yield Label("浏览器 F12 → Application → Cookies 复制整行 Cookie 粘贴:")
                yield Input(placeholder="粘贴 Cookie 字符串…", id="cookie-input")
            with Horizontal(id="login-actions"):
                yield Button("保存 Cookie", id="btn-save-cookie", variant="success")
                yield Button("关闭", id="btn-close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self._stop()
            self.dismiss({})
        elif bid == "btn-save-cookie":
            text = self.query_one("#cookie-input", Input).value.strip()
            if not text:
                self.query_one("#login-status", Label).update("✗ 请先粘贴 Cookie")
                return
            self._cm.set(self._platform, text)
            saved = self._cm.get(self.platform)
            self.query_one("#login-status", Label).update(
                f"✓ 已保存 ({len(saved)} 字符)" if saved else "✗ 保存失败")
            self.dismiss({"cookie_changed": bool(saved)})
        elif bid == "btn-gen-qr":
            self._generate_qr()

    # ---- QR (与 LoginPage._generate_qr/_poll_qr 对应) ----
    def _generate_qr(self):
        from shared.core import LoginBus
        try:
            mgr = LoginBus.get_manager(self.platform)
            if not mgr:
                self.query_one("#login-status", Label).update(
                    f"{self.platform} 不支持扫码登录")
                return
            url, key, img = mgr.generate_qr()
            self._manager = mgr
            self._qr_key = key
            # PIL Image → 终端半块字符画
            art = self._img_to_art(img)
            self.query_one("#qr-art", Label).update(art)
            self.query_one("#login-status", Label).update("请使用 App 扫描二维码")
            self._poll_count = 0
            self.set_interval(3.0, self._poll_qr)
        except Exception as e:
            self.query_one("#login-status", Label).update(f"生成失败: {e}")

    @staticmethod
    def _img_to_art(img) -> str:
        """PIL 图像 → ▀ 半块字符 (白底黑码)。"""
        from PIL import ImageOps
        g = ImageOps.grayscale(img).convert("1")
        w, h = g.size
        px = g.load()
        lines = []
        for y in range(0, h, 2):
            row = []
            for x in range(w):
                top = px[x, y]
                bot = px[x, y + 1] if y + 1 < h else 255
                if not top and not bot:
                    row.append("█")
                elif not top:
                    row.append("▀")
                elif not bot:
                    row.append("▄")
                else:
                    row.append(" ")
            lines.append("".join(row))
        return "\n".join(lines)

    def _poll_qr(self) -> None:
        if not self._qr_key:
            return
        self._poll_count += 1
        if self._poll_count > 100:  # 上限保护
            return
        try:
            from shared.core import LoginBus
            mgr = self._manager or LoginBus.get_manager(self.platform)
            result = mgr.check_qr_status(self._qr_key)
            code = result.get("code", -1)
            if code == 0:
                cookies = result.get("cookies", {})
                cookie_str = ("; ".join(f"{k}={v}" for k, v in cookies.items())
                              if cookies else "")
                if cookie_str:
                    self._cm.set(self.platform, cookie_str)
                    self.query_one("#login-status", Label).update("✓ 登录成功!")
                    self._stop()
                    self.dismiss({"cookie_changed": True})
                else:
                    self.query_one("#login-status", Label).update(
                        "登录成功但未获取到 Cookie")
            elif code == 86090:
                self.query_one("#login-status", Label).update("已扫码, 请在 App 确认…")
            elif code == 86038:
                self.query_one("#login-status", Label).update("二维码已过期, 请刷新")
                self._stop()
        except Exception as e:
            self.query_one("#login-status", Label).update(f"轮询失败: {e}")
            self._stop()

    def _stop(self):
        try:
            if self._manager:
                self._manager.close()
                self._manager = None
        except Exception:
            pass

    def action_dismiss_screen(self) -> None:
        self._stop()
        self.dismiss({})


# ===================== 模态屏: 设置 (对应 SettingsPage) =====================

class SettingsScreen(ModalScreen):
    """设置屏 — 同步 GUI SettingsPage 的核心配置项。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #settings-dlg { width: 72; height: auto; max-height: 90%;
                    border: round $primary; background: $surface; padding: 1 2; }
    """

    _BOOL_FIELDS = ("dedup", "download_danmaku", "download_subtitle",
                    "download_cover", "download_metadata")
    _SELECT_FIELDS = {
        "storage_mode": ["flat", "by_date", "by_author"],
        "storage_format": ["json", "csv"],
        "default_profile": ["mp4_copy", "mp4_h264", "mp3", "png"],
        "default_video_codec": ["copy", "h264", "hevc"],
        "default_audio_codec": ["copy", "aac", "mp3"],
        "default_image_format": ["png", "jpg", "webp"],
    }

    def __init__(self):
        super().__init__()
        self._config = ConfigManager.load()

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        from textual.widgets import Switch

        with Vertical(id="settings-dlg"):
            yield Label("⚙ 设置", classes="dlg-title")
            with VerticalScroll():
                for name in self._SELECT_FIELDS:
                    yield Label(self._field_label(name))
                    cur = getattr(self._config, name)
                    opts = self._SELECT_FIELDS[name]
                    yield Input(value=str(cur), id=f"set-{name}",
                                placeholder=" | ".join(opts))
                for name in self._BOOL_FIELDS:
                    yield Label(self._field_label(name))
                    yield Switch(
                                 value=bool(getattr(self._config, name)),
                                 id=f"set-{name}")
                yield Label(self._field_label("ffmpeg_path"))
                yield Input(value=self._config.ffmpeg_path, id="set-ffmpeg_path",
                            placeholder="留空自动检测")
                yield Label(self._field_label("font_size"))
                yield Input(value=str(self._config.font_size), id="set-font_size",
                            placeholder="12~20")
            with Horizontal(classes="dlg-actions"):
                yield Button("保存", id="btn-save-settings", variant="success")
                yield Button("关闭", id="btn-settings-close")

    @staticmethod
    def _field_label(name: str) -> str:
        return {
            "storage_mode": "存储模式 (flat / by_date / by_author)",
            "storage_format": "数据格式 (json / csv)",
            "dedup": "下载去重",
            "default_profile": "输出预设 (mp4_copy / mp4_h264 / mp3 / png)",
            "default_video_codec": "视频编码 (copy / h264 / hevc)",
            "default_audio_codec": "音频编码 (copy / aac / mp3)",
            "default_image_format": "图片格式 (png / jpg / webp)",
            "download_danmaku": "下载弹幕",
            "download_subtitle": "下载字幕",
            "download_cover": "下载封面",
            "download_metadata": "下载元数据",
            "ffmpeg_path": "FFmpeg 路径 (留空自动检测)",
            "font_size": "字号 (12~20)",
        }.get(name, name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-settings-close":
            self.dismiss(None)
            return
        if event.button.id != "btn-save-settings":
            return
        from textual.widgets import Switch
        cfg = self._config
        try:
            for name, opts in self._SELECT_FIELDS.items():
                v = self.query_one(f"#set-{name}", Input).value.strip()
                if v:
                    if v not in opts:
                        self.notify(f"非法值 {name}={v} (可选: {' | '.join(opts)})",
                                    severity="warning")
                        return
                    setattr(cfg, name, v)
            for name in self._BOOL_FIELDS:
                setattr(cfg, name, self.query_one(f"#set-{name}", Switch).value)
            cfg.ffmpeg_path = self.query_one("#set-ffmpeg_path", Input).value.strip()
            font = int(self.query_one("#set-font_size", Input).value or "14")
            cfg.font_size = max(12, min(20, font))
            ConfigManager.save(cfg)
            self.notify("✓ 设置已保存")
            self.dismiss({"settings_saved": True})
        except Exception as e:
            self.notify(f"✗ 保存失败: {e}", severity="error")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


# ===================== 模态屏: 批量勾选 (对应 WorkGridPage) =====================

class BatchSelectScreen(ModalScreen):
    """批量下载预览勾选 — 对应 GUI WorkGridPage (预览→勾选→下载)。"""

    BINDINGS = [("escape", "dismiss_screen", "取消"),
                ("a", "select_all", "全选"),
                ("n", "select_none", "全不选"),
                ("ctrl+d", "download", "下载勾选")]
    DEFAULT_CSS = """
    BatchSelectScreen { align: center middle; }
    #batch-dlg { width: 90%; height: 85%; border: round $primary;
                 background: $surface; padding: 1 2; }
    #batch-table { height: 1fr; }
    #batch-actions { height: auto; align-horizontal: right; }
    """

    def __init__(self, title: str, items: list[dict]):
        super().__init__()
        self.title_text = title
        self.items = items
        self._checked: set[str] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="batch-dlg"):
            yield Label(f"{self.title_text} ({len(self.items)} 项) — 空格勾选, Ctrl+D 下载",
                        classes="dlg-title")
            table = DataTable(id="batch-table")
            table.cursor_type = "row"
            yield table
            with Horizontal(id="batch-actions"):
                yield Button("全选", id="btn-all")
                yield Button("全不选", id="btn-none")
                yield Button("下载勾选", id="btn-download", variant="success")
                yield Button("取消", id="btn-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#batch-table", DataTable)
        table.add_column("✓", key="check", width=3)
        table.add_column("作品ID")
        table.add_column("标题")
        table.add_column("作者")
        for i, it in enumerate(self.items):
            wid = str(it.get("work_id", i))
            title = (it.get("title") or "")[:40]
            author = it.get("author_name") or it.get("extra") or ""
            table.add_row("☐", wid, title, author, key=wid)

    def _toggle(self, row_key) -> None:
        wid = str(row_key.value)
        table = self.query_one("#batch-table", DataTable)
        if wid in self._checked:
            self._checked.discard(wid)
            table.update_cell(row_key, "check", "☐")
        else:
            self._checked.add(wid)
            table.update_cell(row_key, "check", "☑")

    def on_data_table_row_selected(self, event) -> None:
        self._toggle(event.row_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-all":
            self.action_select_all()
        elif bid == "btn-none":
            self.action_select_none()
        elif bid == "btn-download":
            self.action_download()

    def action_select_all(self) -> None:
        table = self.query_one("#batch-table", DataTable)
        self._checked = set()
        for i, it in enumerate(self.items):
            wid = str(it.get("work_id", i))
            self._checked.add(wid)
        for rk in table.rows:
            table.update_cell(rk, "check", "☑")

    def action_select_none(self) -> None:
        table = self.query_one("#batch-table", DataTable)
        self._checked.clear()
        for rk in table.rows:
            table.update_cell(rk, "check", "☐")

    def action_download(self) -> None:
        self.dismiss(list(self._checked))

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


# ===================== 模态屏: 数据表 (对应 DataTablePage) =====================

class DataTableScreen(ModalScreen):
    """通用数据表屏 — 对应 GUI 数据窗口 (评论/关注/搜索结果等)。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    DataTableScreen { align: center middle; }
    #dt-dlg { width: 95%; height: 90%; border: round $primary;
              background: $surface; padding: 1 2; }
    #dt-table { height: 1fr; }
    """

    def __init__(self, title: str, headers: list[str], rows: list[list]):
        super().__init__()
        self.title_text = title
        self.headers = headers
        self.rows = rows

    def compose(self) -> ComposeResult:
        with Vertical(id="dt-dlg"):
            yield Label(f"{self.title_text} ({len(self.rows)} 行)",
                        classes="dlg-title")
            yield DataTable(id="dt-table")
            yield Button("关闭", id="btn-dt-close")

    def on_mount(self) -> None:
        table = self.query_one("#dt-table", DataTable)
        for h in self.headers:
            table.add_column(h)
        for r in self.rows[:500]:
            table.add_row(*[str(c) for c in r])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-dt-close":
            self.dismiss(None)

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


# ===================== TUI 主应用 =====================

class TuiApp(App):
    """MediaDownloader TUI — 与 GUI MainWindow 布局同步。"""

    TITLE = PROJECT_NAME
    SUB_TITLE = APP_VERSION_LABEL

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("l", "open_login", "登录"),
        Binding("s", "open_settings", "设置"),
        Binding("d", "open_downloads", "下载目录"),
        Binding("ctrl+p", "preview", "解析预览"),
        Binding("ctrl+e", "execute", "执行功能"),
    ]

    CSS = """
    #topbar { height: 3; dock: top; background: $surface;
              border-bottom: solid $primary; }
    #brand { text-style: bold; color: $primary; width: auto; padding: 0 2; }
    .plat-btn { margin: 0 1; min-width: 8; }
    .plat-btn.-active { background: $primary; color: $text; }
    #topbar-right { width: 1fr; }
    #body { height: 1fr; }
    #left-panel { width: 3fr; border: round $primary; padding: 0 1; }
    #right-panel { width: 2fr; }
    #author-card { height: auto; max-height: 10; border-bottom: solid $panel;
                   padding-bottom: 1; }
    #author-title, #work-title, .sec-title {
        text-style: bold; color: $accent; }
    #author-info { color: $text-muted; }
    #work-info { height: 1fr; overflow-y: auto; }
    #link-input { width: 1fr; }
    #features-box { height: 1fr; overflow-y: auto; }
    .feature-btn { width: 1fr; margin: 0 0 1 0; }
    #log-panel { height: 12; border: round $panel; }
    #footer-status { dock: bottom; color: $text-muted; padding: 0 2; }
    .dlg-title { text-style: bold; margin-bottom: 1; }
    .dlg-actions { height: auto; align-horizontal: right; margin-top: 1; }
    """

    def __init__(self):
        super().__init__()
        load_all_platforms()
        self._cm = CookieManager()
        self._platform = ""
        self._current_url = ""
        self._current_user: dict | None = None
        self._author_profile: dict = {}
        self._work: dict = {}
        self._cover_url = ""
        self._current_worker: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_feature = ("", None)  # (feature_id, selected) 供二次执行

    # ---------------- 布局 ----------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="topbar"):
            yield Label("MediaDownloader", id="brand")
            for pid in PlatformBus.list_platforms():
                yield Button(_pn(pid), id=f"plat-{pid}",
                             classes="plat-btn")
            yield Label("", id="topbar-right")
        with Horizontal(id="body"):
            with Vertical(id="left-panel"):
                with Vertical(id="author-card"):
                    yield Label("作者资料", id="author-title")
                    yield Label("未选择平台", id="author-info")
                with Vertical(id="work-info"):
                    yield Label("作品资料", id="work-title")
                    yield Label("粘贴链接 → 解析预览", id="work-detail")
            with Vertical(id="right-panel"):
                yield Label("链接", classes="sec-title")
                yield Input(placeholder="粘贴作品链接 → Ctrl+P 解析预览",
                            id="link-input")
                yield Label("功能", classes="sec-title")
                yield Vertical(id="features-box")
                yield Label("执行日志", classes="sec-title")
                yield RichLog(id="log-panel", wrap=True, markup=False)
        yield Label("", id="footer-status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_features()
        self._refresh_status()
        if "douyin" in PlatformBus.list_platforms():
            self.action_select_platform("douyin")

    # ---------------- 平台切换 (对应 _select_platform) ----------------
    def action_select_platform(self, pid: str) -> None:
        self._platform = pid
        for p in PlatformBus.list_platforms():
            try:
                btn = self.query_one(f"#plat-{p}", Button)
                btn.set_classes(
                    "plat-btn -active" if p == pid else "plat-btn")
            except Exception:
                pass
        self._work = {}
        self._cover_url = ""
        self._refresh_features()
        self._render_author({"nickname": f"已选择 {_pn(pid)}",
                             "signature": "加载当前登录用户…"})
        self.log_line(f"[{_pn(pid)}] 平台已切换", "cyan")
        self._refresh_status()
        cookie = self._cm.get(pid)
        if cookie:
            self._load_current_user(pid, cookie)

    def _refresh_features(self) -> None:
        """重建功能按钮 (对应 FeaturePanel.set_features)。"""
        box = self.query_one("#features-box", Vertical)
        box.remove_children()
        if not self._platform:
            return
        # 作品操作 (对应 GUI work_buttons)
        box.mount(Label("作品操作", classes="sec-title"))
        for i, (label, cb) in enumerate([
            ("获取链接", self._act_copy_link),
            ("查看评论", self._act_comments),
            ("下载封面", self._act_download_cover),
        ]):
            b = Button(label, id=f"act-{i}", classes="feature-btn")
            b.handlers = cb  # type: ignore[attr-defined]
            box.mount(b)
        # 作者操作 (对应 author_buttons)
        box.mount(Label("作者操作", classes="sec-title"))
        for i, (label, cb) in enumerate([
            ("获取作品", self._act_fetch_works),
            ("关注列表", self._act_follow_list),
            ("收藏列表", self._act_collect_list),
            ("下载头像", self._act_download_avatar),
            ("获取主页", self._act_open_home),
        ]):
            b = Button(label, id=f"auact-{i}", classes="feature-btn")
            b.handlers = cb  # type: ignore[attr-defined]
            box.mount(b)
        # 平台功能 (FeatureMeta 动态)
        feats = PlatformBus.get_features(self._platform)
        if feats:
            box.mount(Label("平台功能", classes="sec-title"))
            for f in feats:
                b = Button(f.name, classes="feature-btn")
                b.id = f"feat-{f.id}"
                b.feature_id = f.id  # type: ignore[attr-defined]
                box.mount(b)

    def _refresh_status(self) -> None:
        """底部状态栏 (对应 _refresh_cookie_status)。"""
        parts = []
        if not self._platform:
            parts.append("未选择平台")
        else:
            cookie = self._cm.get(self._platform)
            name = _pn(self._platform)
            if cookie and cookie.strip():
                hint = self._cookie_key_hint(self._platform)
                if hint and not all(k in cookie for k in hint.split("|")):
                    parts.append(f"{name}: ⚠ Cookie 不完整 (建议含 {hint})")
                else:
                    parts.append(f"{name}: ✓ Cookie 已配置 ({len(cookie)} 字符)")
            else:
                parts.append(f"{name}: ✗ Cookie 未配置")
        ok, _ = FFmpegManager.check_available()
        parts.append(f"FFmpeg {'✓' if ok else '✗'}")
        parts.append(APP_VERSION_LABEL)
        self.query_one("#footer-status", Label).update("  |  ".join(parts))

    @staticmethod
    def _cookie_key_hint(platform: str) -> str:
        return {
            "douyin": "ttwid|msToken|sessionid",
            "bilibili": "SESSDATA|bili_jct",
            "kuaishou": "did",
            "xiaohongshu": "web_session",
        }.get(platform, "")

    # ---------------- 事件 ----------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("plat-"):
            self.action_select_platform(bid[5:])
            return
        if bid.startswith("feat-"):
            self.action_execute(bid[5:])
            return
        cb = getattr(event.button, "handlers", None)
        if cb:
            cb()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "link-input":
            self.action_preview()

    # ---------------- 日志 ----------------
    def log_line(self, msg: str, color: str = "") -> None:
        """线程安全写日志 (对应 LogPanel.append)。"""
        def _write():
            log = self.query_one("#log-panel", RichLog)
            if color:
                log.write(f"[{color}]{msg}[/{color}]")
            else:
                c = _color_of(msg)
                log.write(f"[{c}]{msg}[/{c}]" if c else msg)
        try:
            self.call_from_thread(_write)
        except Exception:
            pass

    # ---------------- 后台线程执行 (对应 FeatureWorker) ----------------
    def _run_bg(self, coro_factory, on_done=None, name="task") -> None:
        """在后台线程的事件循环里执行协程, 完成后回主线程回调。"""
        if self._current_worker and self._current_worker.is_alive():
            self.log_line("⚠ 有任务正在执行, 请稍候", "yellow")
            return

        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro_factory())
                if on_done:
                    self.call_from_thread(on_done, result)
            except Exception as e:
                self.log_line(f"✗ {name} 异常: {e}", "red")
            finally:
                loop.close()

        self._current_worker = threading.Thread(target=_runner, daemon=True)
        self._current_worker.start()

    # ---------------- 当前用户 (对应 _load_current_user) ----------------
    def _load_current_user(self, platform: str, cookie: str) -> None:
        self.log_line("▸ 获取当前登录用户...", "cyan")
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform

        async def _fetch():
            cls = get_platform(platform)
            if not cls:
                return None
            a = cls(config=PlatformConfig(
                name=platform, display_name=platform,
                domains=[], cookie=cookie))
            try:
                if hasattr(a, "fetch_current_user"):
                    return await asyncio.wait_for(a.fetch_current_user(), 15)
                return None
            finally:
                await a.close()

        def _done(result):
            if not result:
                self.log_line("✗ 未获取到用户 (Cookie 可能失效)", "red")
                return
            self.log_line(f"✓ 当前用户: {result.get('nickname', '?')}", "green")
            self._current_user = result
            self._render_author(result)

        self._run_bg(_fetch, _done, "当前用户")

    def _render_author(self, p: dict) -> None:
        self._author_profile = p
        info = self.query_one("#author-info", Label)
        name = p.get("nickname") or p.get("nickname", "") or "?"
        sign = (p.get("signature") or "")[:50]
        fans = p.get("follower_count", 0)
        follow = p.get("following_count", 0)
        liked = p.get("total_favorited", 0)
        works = p.get("aweme_count", 0)
        info.update(
            f"{name}\n{sign or '—'}\n"
            f"粉丝 {fans} · 关注 {follow} · 获赞 {liked} · 作品 {works}")

    def _render_work(self, w: dict) -> None:
        self._work = w
        detail = self.query_one("#work-detail", Label)
        title = (w.get("title") or "")[:60]
        author = w.get("author_name") or "?"
        dur = w.get("duration") or 0
        digg = w.get("digg_count", "")
        url = w.get("share_url") or ""
        detail.update(
            f"标题: {title or '—'}\n作者: {author}\n时长: {dur}s"
            + (f"\n点赞: {digg}" if digg != "" else "")
            + (f"\n链接: {url[:70]}" if url else ""))

    # ---------------- 解析预览 (对应 _on_preview/_do_preview) ----------------
    def action_preview(self) -> None:
        url = self.query_one("#link-input", Input).value.strip()
        if not url:
            if not self._platform:
                self.log_line("⚠ 请先选择平台", "yellow")
                return
            cookie = self._cm.get(self._platform)
            if not cookie:
                self.log_line("⚠ 未配置 Cookie", "yellow")
                return
            self._load_current_user(self._platform, cookie)
            return
        if not self._platform:
            self.log_line("⚠ 请先选择平台", "yellow")
            return
        self._current_url = url
        self.log_line(f"[{_pn(self._platform)}] 正在解析 {url[:60]}...", "cyan")

        async def _do():
            from shared.core.session import create_async_client
            from shared.flow.link import LinkExtractor
            from shared.core.adapter import PlatformConfig
            from platforms import get_platform
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, self._platform)
            finally:
                await client.close()
            if not links:
                return None
            adapter_cls = get_platform(self._platform)
            a = adapter_cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                raw = await a.request_detail(links[0])
                return a.parse_detail(raw) if raw else None
            finally:
                await a.close()

        def _done(work):
            if not work:
                self.log_line("✗ 解析失败, 未获取到作品资料", "red")
                return
            self.log_line(f"✓ 解析成功: {work.get('title', '')[:40]}", "green")
            # 归一化字段
            from shared.core import norm_work
            self._render_work(norm_work(work, self._platform))
            self._cover_url = work.get("cover") or ""

        self._run_bg(_do, _done, "解析预览")

    # ---------------- 功能执行 (对应 _on_execute + FeatureWorker) ----------------
    def action_execute(self, feature_id: str) -> None:
        if not self._platform:
            self.log_line("⚠ 请先选择平台", "yellow")
            return
        ops = PlatformBus.get_ops(self._platform)
        feat = next((f for f in (ops.features if ops else [])
                     if f.id == feature_id), None)
        if feat and feat.need_url and not self._current_url:
            self.log_line(f"⚠ [{feat.name}] 需要先粘贴并解析链接", "yellow")
            return
        self._stop_event.clear()
        self._last_feature = (feature_id, None)
        self._run_feature(feature_id, None)

    def _run_feature(self, feature_id: str, selected: list[str] | None) -> None:
        cookie = self._cm.get(self._platform)
        save_dir = VOLUME / self._platform
        save_dir.mkdir(parents=True, exist_ok=True)

        async def _do():
            return await PlatformBus.run(
                self._platform, feature_id, self._current_url,
                cookie, save_dir, on_log=lambda m: self.log_line(str(m)),
                selected=selected, stop_event=self._stop_event)

        def _done(result):
            for line in (result.log or [])[-10:]:
                self.log_line(line)
            if result.preview == "batch" and result.data:
                self._open_batch_select(result.message, result.data,
                                        feature_id)
                return
            if result.data and feature_id in {
                    "download", "account", "series", "collection",
                    "collection_album", "mix", "live"} and not result.preview:
                from shared.core import norm_work
                self._render_work(norm_work(result.data[0], self._platform))
            self.log_line(
                ("✓ " if result.success else "✗ ") + result.message,
                "green" if result.success else "red")
            self._refresh_status()

        self._run_bg(_do, _done, f"功能 {feature_id}")

    def _open_batch_select(self, title: str, items: list[dict],
                           feature_id: str) -> None:
        def _cb(selected):
            if selected:
                self.log_line(f"✓ 已勾选 {len(selected)} 项, 开始下载", "green")
                self._last_feature = (feature_id, selected)
                self._run_feature(feature_id, selected)
        self.push_screen(BatchSelectScreen(title, items), _cb)

    # ---------------- 作者/作品 操作 (对应 GUI 按钮) ----------------
    def _act_copy_link(self) -> None:
        url = self._work.get("share_url") or ""
        if url:
            self.log_line(f"✓ 作品链接: {url}", "green")
        else:
            self.log_line("⚠ 无作品链接 (先解析预览)", "yellow")

    def _act_comments(self) -> None:
        wid = str(self._work.get("work_id", ""))
        if not wid:
            self.log_line("⚠ 无作品ID (先解析预览)", "yellow")
            return
        self.log_line(f"▸ 获取评论: {wid}", "cyan")

        async def _do():
            from shared.core.adapter import PlatformConfig, norm_comment
            from platforms import get_platform
            cls = get_platform(self._platform)
            a = cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                data = await a.fetch_comments(wid)
                if isinstance(data, dict):
                    data = data.get("comments") or data.get("data") or []
                return [norm_comment(c) for c in (data or []) if isinstance(c, dict)]
            finally:
                await a.close()

        def _done(items):
            items = [c for c in items if c.get("content")]
            if not items:
                self.log_line("⚠ 评论: 没有数据", "yellow")
                return
            rows = [[c.get("nickname", "—"), c.get("content", "")]
                    for c in items]
            self.push_screen(DataTableScreen("评论列表", ["用户", "内容"], rows))
            self.log_line(f"✓ 评论 {len(items)} 条", "green")

        self._run_bg(_do, _done, "评论")

    def _act_download_cover(self) -> None:
        url = self._cover_url
        if not url:
            self.log_line("⚠ 无封面地址 (先解析预览)", "yellow")
            return

        async def _do():
            import time
            from curl_cffi.requests import get as _get
            r = await asyncio.to_thread(
                _get, url, timeout=15, impersonate="chrome146")
            d = VOLUME / (self._platform or "common") / "covers"
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"cover_{int(time.time())}.jpg"
            path.write_bytes(bytes(r.content))
            return str(path)

        def _done(path):
            self.log_line(f"✓ 封面已保存: {path}", "green")

        self._run_bg(_do, _done, "封面下载")

    def _act_download_avatar(self) -> None:
        url = (self._author_profile or {}).get("avatar", "")
        if not url:
            self.log_line("⚠ 无头像地址", "yellow")
            return

        async def _do():
            import time
            from curl_cffi.requests import get as _get
            r = await asyncio.to_thread(
                _get, url, timeout=15, impersonate="chrome146")
            d = VOLUME / (self._platform or "common") / "avatars"
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"avatar_{int(time.time())}.jpg"
            path.write_bytes(bytes(r.content))
            return str(path)

        def _done(path):
            self.log_line(f"✓ 头像已保存: {path}", "green")

        self._run_bg(_do, _done, "头像下载")

    def _sec_uid(self) -> str:
        prof = self._author_profile or {}
        return (prof.get("sec_user_id") or prof.get("sec_uid")
                or prof.get("user_id") or "")

    def _act_fetch_works(self) -> None:
        sec = self._sec_uid()
        if not sec:
            self.log_line("⚠ 未获取到作者 sec_user_id", "yellow")
            return
        self.log_line("▸ 获取作者所有作品...", "cyan")

        async def _do():
            from shared.core.adapter import PlatformConfig, norm_work
            from platforms import get_platform
            cls = get_platform(self._platform)
            a = cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                items = []
                cursor = "0"
                for _ in range(5):
                    data = await a.fetch_user_posts(sec, count=20, max_cursor=cursor)
                    if not data:
                        break
                    if isinstance(data, list):
                        items = [norm_work(w, self._platform) for w in data]
                        break
                    aws = data.get("aweme_list") or []
                    if not aws:
                        break
                    items.extend(norm_work(w, self._platform) for w in aws)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("max_cursor") or "0")
                    if cursor == "0":
                        break
                return items
            finally:
                await a.close()

        def _done(items):
            if not items:
                self.log_line("⚠ 没有作品数据", "yellow")
                return
            self.push_screen(DataTableScreen(
                "作者所有作品",
                ["标题", "作者", "时长(s)"],
                [[w.get("title", "")[:40], w.get("author_name", ""),
                  str(w.get("duration", 0))] for w in items]))
            self.log_line(f"✓ 共 {len(items)} 个作品", "green")

        self._run_bg(_do, _done, "作者作品")

    def _act_follow_list(self) -> None:
        prof = self._current_user or self._author_profile or {}
        sec = prof.get("sec_user_id") or prof.get("sec_uid") or ""
        if not sec:
            self.log_line("⚠ 未获取到当前登录用户", "yellow")
            return
        self.log_line("▸ 拉取关注列表...", "cyan")

        async def _do():
            from shared.core.adapter import PlatformConfig, norm_user
            from platforms import get_platform
            cls = get_platform(self._platform)
            a = cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                data = await a.fetch_user_following(sec, count=20, max_time="0")
                if isinstance(data, list):
                    return [norm_user(u, self._platform) for u in data]
                fl = (data or {}).get("followings") or (data or {}).get("follow_list") or []
                return [norm_user(u, self._platform) for u in fl]
            finally:
                await a.close()

        def _done(users):
            if not users:
                self.log_line("⚠ 关注列表: 没有数据", "yellow")
                return
            self.push_screen(DataTableScreen(
                "关注列表", ["昵称", "签名", "粉丝"],
                [[u.get("nickname", ""), (u.get("signature") or "")[:30],
                  str(u.get("follower_count", 0))] for u in users]))
            self.log_line(f"✓ 共 {len(users)} 个关注", "green")

        self._run_bg(_do, _done, "关注列表")

    def _act_collect_list(self) -> None:
        self.log_line("▸ 拉取收藏列表...", "cyan")

        async def _do():
            from shared.core.adapter import PlatformConfig, norm_work
            from platforms import get_platform
            cls = get_platform(self._platform)
            a = cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                data = await a.fetch_collection(cursor="0", count=20)
                if isinstance(data, list):
                    return [norm_work(w, self._platform) for w in data]
                aws = (data or {}).get("aweme_list") or []
                return [norm_work(w, self._platform) for w in aws]
            finally:
                await a.close()

        def _done(items):
            if not items:
                self.log_line("⚠ 收藏列表: 没有数据", "yellow")
                return
            self.push_screen(DataTableScreen(
                "收藏列表", ["标题", "作者", "时长(s)"],
                [[w.get("title", "")[:40], w.get("author_name", ""),
                  str(w.get("duration", 0))] for w in items]))
            self.log_line(f"✓ 共 {len(items)} 个收藏", "green")

        self._run_bg(_do, _done, "收藏列表")

    def _act_open_home(self) -> None:
        sec = self._sec_uid()
        p = (self._author_profile or {}).get("platform") or self._platform
        if not sec:
            self.log_line("⚠ 无作者主页链接", "yellow")
            return
        if p == "bilibili":
            home = f"https://space.bilibili.com/{sec}"
        elif p == "kuaishou":
            home = f"https://www.kuaishou.com/profile/{sec}"
        elif p == "xiaohongshu":
            home = f"https://www.xiaohongshu.com/user/profile/{sec}"
        else:
            home = f"https://www.douyin.com/user/{sec}"
        self.log_line(f"✓ 作者主页: {home}", "green")

    # ---------------- 模态屏入口 ----------------
    def action_open_login(self) -> None:
        if not self._platform:
            self.notify("请先选择平台", severity="warning")
            return
        try:
            ops = PlatformBus.get_ops(self._platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self.push_screen(LoginScreen(self._platform, hint),
                         self._after_login)

    def _after_login(self, result) -> None:
        if result and result.get("cookie_changed"):
            self._refresh_status()
            cookie = self._cm.get(self._platform)
            if cookie:
                self._load_current_user(self._platform, cookie)

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._after_settings)

    def _after_settings(self, result) -> None:
        if result and result.get("settings_saved"):
            self._refresh_status()

    def action_open_downloads(self) -> None:
        self.log_line(f"下载目录: {VOLUME}", "cyan")

    # ---------------- 停止录制 (对应 _on_stop_recording) ----------------
    def action_stop_recording(self) -> None:
        self._stop_event.set()
        self.log_line("■ 已请求停止录制/任务", "yellow")
