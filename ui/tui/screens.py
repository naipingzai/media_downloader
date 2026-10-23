"""TUI 模态屏 (精简版) — 只保留下载相关: 登录 / 设置 / 批量勾选。"""
from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static


# ===================== 登录屏 =====================

class LoginScreen(ModalScreen):
    """登录 — QR 终端字符画 + Cookie 粘贴。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    LoginScreen { align: center middle; }
    #login-dlg { width: 68; height: auto; max-height: 92%;
                 border: round $primary; background: $surface; padding: 1 2; }
    #login-title { text-style: bold; margin-bottom: 1; }
    #login-scroll { height: auto; max-height: 26; }
    #qr-art { background: white; color: black; padding: 0 1; width: auto; }
    #login-status { color: $warning; margin-top: 1; }
    #login-actions { height: auto; align-horizontal: right; margin-top: 1; }
    """

    def __init__(self, platform: str, cookie_hint: str = ""):
        super().__init__()
        self.platform = platform
        self.cookie_hint = cookie_hint
        self._cm = None
        self._qr_key = ""
        self._manager = None
        self._poll_count = 0

    def compose(self):
        from shared.core import CookieManager, LoginBus, platform_name as _pn
        self._cm = CookieManager()
        cur = self._cm.get(self.platform)
        with Vertical(id="login-dlg"):
            yield Label(f"登录 · {_pn(self.platform)}", id="login-title")
            status = (f"● 已配置 Cookie ({len(cur)} 字符)" if cur
                      else "● 未配置 Cookie")
            yield Label(status, id="login-status")
            with VerticalScroll(id="login-scroll"):
                if LoginBus.has_qr(self.platform):
                    yield Label("扫码登录 — 用 App 扫描二维码")
                    yield Static("点击「生成二维码」", id="qr-art")
                if self.cookie_hint:
                    yield Label(f"建议 Cookie 包含: {self.cookie_hint}")
                yield Label("手动: 浏览器 F12 → Application → Cookies 复制整行:")
                yield Input(placeholder="粘贴 Cookie 字符串…", id="cookie-input")
            with Horizontal(id="login-actions"):
                if LoginBus.has_qr(self.platform):
                    yield Button("生成二维码", id="btn-gen-qr", variant="primary")
                yield Button("保存 Cookie", id="btn-save-cookie", variant="success")
                yield Button("关闭", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self._stop_manager()
            self.dismiss({})
        elif bid == "btn-save-cookie":
            self._save_cookie()
        elif bid == "btn-gen-qr":
            self._generate_qr()

    def _save_cookie(self) -> None:
        text = self.query_one("#cookie-input", Input).value.strip()
        status = self.query_one("#login-status", Label)
        if not text:
            status.update("✗ 请先粘贴 Cookie")
            return
        self._cm.set(self.platform, text)
        saved = self._cm.get(self.platform)
        if saved:
            status.update(f"✓ 已保存 ({len(saved)} 字符)")
            self._stop_manager()
            self.dismiss({"cookie_changed": True})
        else:
            status.update("✗ 保存失败")

    def _generate_qr(self) -> None:
        from shared.core import LoginBus
        try:
            mgr = LoginBus.get_manager(self.platform)
            if not mgr:
                self.query_one("#login-status", Label).update(
                    f"{self.platform} 不支持扫码登录")
                return
            _url, key, img = mgr.generate_qr()
            self._manager = mgr
            self._qr_key = key
            self.query_one("#qr-art", Static).update(self._img_to_art(img))
            self.query_one("#login-status", Label).update("请用 App 扫描二维码")
            self._poll_count = 0
            self.set_interval(3.0, self._poll_qr)
        except Exception as e:
            self.query_one("#login-status", Label).update(f"生成失败: {e}")

    @staticmethod
    def _img_to_art(img) -> str:
        """PIL 图像 → ▀▄█ 半块字符 (白底黑码)。"""
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
            lines.append("".join(row).rstrip())
        return "\n".join(lines)

    def _poll_qr(self) -> None:
        if not self._qr_key:
            return
        self._poll_count += 1
        if self._poll_count > 100:
            return
        try:
            from shared.core import LoginBus
            mgr = self._manager or LoginBus.get_manager(self.platform)
            result = mgr.check_qr_status(self._qr_key)
            code = result.get("code", -1)
            status = self.query_one("#login-status", Label)
            if code == 0:
                cookies = result.get("cookies", {})
                cookie_str = ("; ".join(f"{k}={v}" for k, v in cookies.items())
                              if cookies else "")
                if cookie_str:
                    self._cm.set(self.platform, cookie_str)
                    status.update("✓ 登录成功!")
                    self._stop_manager()
                    self.dismiss({"cookie_changed": True})
                else:
                    status.update("登录成功但未获取到 Cookie")
            elif code == 86090:
                status.update("已扫码, 请在 App 中确认…")
            elif code == 86038:
                status.update("二维码已过期, 请重新生成")
                self._stop_manager()
        except Exception as e:
            self.query_one("#login-status", Label).update(f"轮询失败: {e}")
            self._stop_manager()

    def _stop_manager(self):
        try:
            if self._manager:
                self._manager.close()
                self._manager = None
        except Exception:
            pass

    def action_dismiss_screen(self) -> None:
        self._stop_manager()
        self.dismiss({})


# ===================== 设置屏 =====================

class SettingsScreen(ModalScreen):
    """设置 — 存储/输出/下载/FFmpeg。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #settings-dlg { width: 76; height: auto; max-height: 92%;
                    border: round $primary; background: $surface; padding: 1 2; }
    .set-label { margin-top: 1; }
    .dlg-actions { height: auto; align-horizontal: right; margin-top: 1; }
    .dlg-title { text-style: bold; margin-bottom: 1; }
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
    _LABELS = {
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
    }

    def __init__(self):
        super().__init__()
        self._config = None

    def compose(self):
        from shared.core import ConfigManager
        from textual.widgets import Switch
        self._config = ConfigManager.load()
        with Vertical(id="settings-dlg"):
            yield Label("⚙ 设置", classes="dlg-title")
            with VerticalScroll():
                for name, opts in self._SELECT_FIELDS.items():
                    yield Label(self._LABELS[name], classes="set-label")
                    yield Input(value=str(getattr(self._config, name)),
                                id=f"set-{name}", placeholder=" | ".join(opts))
                for name in self._BOOL_FIELDS:
                    yield Label(self._LABELS[name], classes="set-label")
                    yield Switch(value=bool(getattr(self._config, name)),
                                 id=f"set-{name}")
                yield Label(self._LABELS["ffmpeg_path"], classes="set-label")
                yield Input(value=self._config.ffmpeg_path,
                            id="set-ffmpeg_path", placeholder="留空自动检测")
                yield Label(self._LABELS["font_size"], classes="set-label")
                yield Input(value=str(self._config.font_size),
                            id="set-font_size", placeholder="12~20")
            with Horizontal(classes="dlg-actions"):
                yield Button("保存", id="btn-save-settings", variant="success")
                yield Button("关闭", id="btn-settings-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-settings-close":
            self.dismiss(None)
            return
        if event.button.id != "btn-save-settings":
            return
        from shared.core import ConfigManager
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
            cfg.font_size = max(12, min(20, int(
                self.query_one("#set-font_size", Input).value or "14")))
            ConfigManager.save(cfg)
            self.notify("✓ 设置已保存")
            self.dismiss({"settings_saved": True})
        except Exception as e:
            self.notify(f"✗ 保存失败: {e}", severity="error")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


# ===================== 批量勾选屏 =====================

class BatchSelectScreen(ModalScreen):
    """批量下载勾选 — 空格勾选 + Ctrl+D 下载。"""

    BINDINGS = [("escape", "dismiss_screen", "取消"),
                ("a", "select_all", "全选"),
                ("n", "select_none", "全不选"),
                ("ctrl+d", "download", "下载勾选")]
    DEFAULT_CSS = """
    BatchSelectScreen { align: center middle; }
    #batch-dlg { width: 94%; height: 90%; border: round $primary;
                 background: $surface; padding: 1 2; }
    #batch-table { height: 1fr; }
    #batch-actions { height: auto; align-horizontal: right; margin-top: 1; }
    .dlg-title { text-style: bold; margin-bottom: 1; }
    """

    def __init__(self, title: str, items: list):
        super().__init__()
        self.title_text = title
        self.items = items
        self._checked: set = set()

    def compose(self):
        with Vertical(id="batch-dlg"):
            yield Label(f"{self.title_text} · {len(self.items)} 项 — "
                        "空格勾选, A 全选, N 全不选, Ctrl+D 下载",
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
        table.add_column("作品ID", width=20)
        table.add_column("标题")
        table.add_column("作者")
        for i, it in enumerate(self.items):
            wid = str(it.get("work_id", i))
            table.add_row("☐", wid, (it.get("title") or "")[:50],
                          it.get("author_name") or it.get("extra") or "", key=wid)

    def on_data_table_row_selected(self, event) -> None:
        wid = str(event.row_key.value)
        table = self.query_one("#batch-table", DataTable)
        if wid in self._checked:
            self._checked.discard(wid)
            table.update_cell(event.row_key, "check", "☐")
        else:
            self._checked.add(wid)
            table.update_cell(event.row_key, "check", "☑")

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
        self._checked = {str(it.get("work_id", i)) for i, it in enumerate(self.items)}
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


# ===================== 数据表屏 (作品/关注/收藏/评论 列表) =====================

class DataTableScreen(ModalScreen):
    """通用数据表 — 作品/关注/收藏/评论/搜索结果 列表展示。"""

    BINDINGS = [("escape", "dismiss_screen", "关闭")]
    DEFAULT_CSS = """
    DataTableScreen { align: center middle; }
    #dt-dlg { width: 96%; height: 92%; border: round $primary;
              background: $surface; padding: 1 2; }
    #dt-table { height: 1fr; }
    .dlg-title { text-style: bold; margin-bottom: 1; }
    """

    def __init__(self, title: str, headers: list, rows: list):
        super().__init__()
        self.title_text = title
        self.headers = headers
        self.rows = rows

    def compose(self):
        with Vertical(id="dt-dlg"):
            yield Label(f"{self.title_text} · {len(self.rows)} 行",
                        classes="dlg-title")
            yield DataTable(id="dt-table")
            yield Button("关闭", id="btn-dt-close")

    def on_mount(self) -> None:
        table = self.query_one("#dt-table", DataTable)
        for h in self.headers:
            table.add_column(h)
        for r in self.rows[:1000]:
            table.add_row(*[str(c) for c in r])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-dt-close":
            self.dismiss(None)

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)
