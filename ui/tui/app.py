"""TUI 精简版 — 仅保留下载功能。

界面 (极简单列):
  ┌───────────────────────────────┐
  │ 平台: [抖音] [B站] [快手] [小红书]│
  │ 🔗 [链接输入        ] [解析预览] │
  │ ▶ 当前作品: 标题/类型           │
  │ ⬇ 下载 | ⬇ 批量下载 | 🔴停止录制│
  │ 📋 下载功能: 合集/收藏/直播…    │
  │ [登录] [设置]                  │
  │ 💬 状态: ...                   │
  └───────────────────────────────┘
功能: 解析预览 / 下载作品 / 批量下载(勾选) / 直播录制 / 合集 / 收藏夹
      不做资料卡、评论、列表、日志面板
"""
from __future__ import annotations


import re
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Static

from shared.core import (
    PROJECT_NAME, VOLUME, CookieManager, PlatformBus,
    platform_name as _pn,
)
from platforms import load_all_platforms
from .screens import BatchSelectScreen, LoginScreen, SettingsScreen

APP_VERSION_LABEL = "TUI"

# 只保留下载相关的平台功能
_DOWNLOAD_FEATURES = {"download", "account", "mix", "series",
                      "collection", "collection_album", "favorite_folder",
                      "live", "tk_download", "ks_download", "xhs_download"}


class TuiApp(App):
    """MediaDownloader TUI — 精简下载工具。"""

    TITLE = PROJECT_NAME
    SUB_TITLE = APP_VERSION_LABEL

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("l", "open_login", "登录"),
        Binding("s", "open_settings", "设置"),
        Binding("ctrl+p", "preview", "解析预览"),
        Binding("x", "stop_task", "停止"),
    ]

    CSS = """
    Screen { layout: vertical; padding: 1 2; }
    #plat-row { height: 3; margin-bottom: 1; }
    #plat-label { text-style: bold; color: $primary; padding: 0 1; }
    .plat-btn { margin: 0 1; min-width: 8; height: 3; }
    .plat-btn.-active { background: $primary; color: $text; text-style: bold; }
    #link-row { height: 3; margin-bottom: 1; }
    #link-input { width: 1fr; }
    #work-info { height: auto; margin-bottom: 1; padding: 0 1;
                 border: round $panel; color: $text; }
    #dl-row { height: 3; margin-bottom: 1; }
    .dl-btn { margin: 0 1; height: 3; }
    #feat-label { text-style: bold; color: $accent; padding: 0 1; }
    #feat-scroll { height: auto; max-height: 16; margin-bottom: 1; }
    .menu-btn { width: 1fr; height: 3; margin: 0 1; }
    #sys-row { height: 3; margin-bottom: 1; }
    .sys-btn { margin: 0 1; height: 3; }
    #status-line { height: auto; color: $text-muted; padding: 0 1; }
    #footer-status { dock: bottom; color: $text-muted; padding: 0 1;
                     background: $surface; }
    """

    MAX_FEATURES = 12

    def __init__(self):
        super().__init__()
        load_all_platforms()
        self._cm = CookieManager()
        self._platform = ""
        self._current_url = ""
        self._work: dict = {}
        self._norm_work: dict = {}
        self._task_guard: set = set()
        self._stop_event = threading.Event()

    # ---------------- 布局 ----------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        # 平台切换
        with Horizontal(id="plat-row"):
            yield Label("平台:", id="plat-label")
            for pid in PlatformBus.list_platforms():
                yield Button(_pn(pid), id=f"plat-{pid}", classes="plat-btn")
        # 链接输入
        with Horizontal(id="link-row"):
            yield Input(placeholder="粘贴作品链接/分享文本 → Ctrl+P 解析预览",
                        id="link-input")
            yield Button("解析预览", id="act-preview", variant="primary")
        # 当前作品信息 (单行文本)
        yield Static("未解析 — 粘贴链接后按 [解析预览]", id="work-info")
        # 下载按钮行
        with Horizontal(id="dl-row"):
            yield Button("⬇ 下载作品", id="act-dl", classes="dl-btn",
                         variant="success")
            yield Button("⬇ 批量下载账号", id="act-account", classes="dl-btn")
            yield Button("🔴 停止录制", id="act-stop", classes="dl-btn",
                         variant="error")
        # 平台下载功能 (预建按钮, 避免 remove_children/mount 挂起)
        yield Label("📋 下载功能", id="feat-label")
        with VerticalScroll(id="feat-scroll"):
            for i in range(self.MAX_FEATURES):
                b = Button("", id=f"feat-{i}", classes="menu-btn")
                b.feature_id = ""  # type: ignore[attr-defined]
                b.display = False
                yield b
        # 系统
        with Horizontal(id="sys-row"):
            yield Button("🔑 登录 (l)", id="sys-login", classes="sys-btn")
            yield Button("⚙ 设置 (s)", id="sys-settings", classes="sys-btn")
        # 状态行 (结果提示, 非日志)
        yield Static("", id="status-line")
        yield Label("", id="footer-status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_menu()
        self._refresh_status()
        if "douyin" in PlatformBus.list_platforms():
            self._select_platform("douyin")

    # ---------------- 平台切换 (修复闪退: 全部 try/except + 不触发网络) ----------------
    def _select_platform(self, pid: str) -> None:
        try:
            self._platform = pid
            for p in PlatformBus.list_platforms():
                try:
                    btn = self.query_one(f"#plat-{p}", Button)
                    btn.set_classes("plat-btn -active" if p == pid else "plat-btn")
                except Exception:
                    pass
            self._work = {}
            self._norm_work = {}
            self._refresh_menu()
            self._set_info(f"已切换到 {_pn(pid)} — 粘贴链接后按 [解析预览]")
            self._refresh_status()
        except Exception as e:
            self._set_info(f"⚠ 切换平台异常: {e}")

    def _refresh_menu(self) -> None:
        """更新下载功能按钮 (仅下载相关) — 纯属性更新, 无 async 挂起。"""
        try:
            btns = list(self.query(".menu-btn"))
            feats = [f for f in PlatformBus.get_features(self._platform)
                     if f.id in _DOWNLOAD_FEATURES] if self._platform else []
            for i, b in enumerate(btns):
                if i < len(feats):
                    b.label = feats[i].name
                    b.feature_id = feats[i].id  # type: ignore[attr-defined]
                    b.display = True
                else:
                    b.label = ""
                    b.feature_id = ""  # type: ignore[attr-defined]
                    b.display = False
        except Exception:
            pass

    def _refresh_status(self) -> None:
        try:
            parts = []
            if not self._platform:
                parts.append("未选择平台")
            else:
                cookie = self._cm.get(self._platform)
                name = _pn(self._platform)
                if cookie and cookie.strip():
                    parts.append(f"{name}: ✓ Cookie 已配置 ({len(cookie)} 字符)")
                else:
                    parts.append(f"{name}: ✗ 未配置 Cookie (l 登录)")
            parts.append(f"下载目录: {VOLUME}")
            self.query_one("#footer-status", Label).update("  |  ".join(parts))
        except Exception:
            pass

    # ---------------- 状态行 (替代日志面板) ----------------
    def _set_info(self, msg: str) -> None:
        try:
            self.query_one("#status-line", Static).update(msg)
        except Exception:
            pass

    # ---------------- 事件 ----------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            bid = event.button.id or ""
            if bid.startswith("plat-"):
                self._select_platform(bid[5:])
                return
            if bid.startswith("feat-"):
                fid = getattr(event.button, "feature_id", "") or ""
                if fid:
                    self.action_execute(fid)
                return
            handler = {
                "act-preview": self.action_preview,
                "act-dl": lambda: self.action_execute("download"),
                "act-account": lambda: self.action_execute("account"),
                "act-stop": self.action_stop_task,
                "sys-login": self.action_open_login,
                "sys-settings": self.action_open_settings,
            }.get(bid)
            if handler:
                handler()
        except Exception as e:
            self._set_info(f"⚠ 异常: {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "link-input":
            self.action_preview()

    # ---------------- 后台任务 ----------------
    def _run_task(self, coro, on_done=None, name="task",
                  guard_key: str = "") -> None:
        if guard_key and guard_key in self._task_guard:
            self._set_info(f"⚠ [{name}] 已在执行中 (x 可停止)")
            coro.close()
            return
        if guard_key:
            self._task_guard.add(guard_key)

        async def _wrapped():
            try:
                result = await coro
            except Exception as e:
                self._set_info(f"✗ {name} 失败: {type(e).__name__}: {e}")
                result = None
            finally:
                if guard_key:
                    self._task_guard.discard(guard_key)
            if on_done:
                try:
                    on_done(result)
                except Exception as e:
                    self._set_info(f"✗ 回调异常: {e}")

        self.run_worker(_wrapped(), exclusive=False, group="task",
                        description=name)

    def action_stop_task(self) -> None:
        self._stop_event.set()
        self._set_info("■ 已请求停止录制/任务")

    # ---------------- 解析预览 ----------------
    def action_preview(self) -> None:
        if not self._platform:
            self._set_info("⚠ 请先选择平台")
            return
        raw = self.query_one("#link-input", Input).value.strip()
        if not raw:
            self._set_info("⚠ 请粘贴作品链接")
            return
        m = re.search(r"https?://\S+", raw)
        if not m:
            self._set_info("⚠ 未找到有效链接")
            return
        url = m.group(0)
        for junk in ("复制此链接", "打开Dou音", "，", "。", "！", ")", "）"):
            url = url.split(junk)[0]
        url = url.rstrip("/ ")
        self._current_url = url
        self._set_info(f"[{_pn(self._platform)}] 正在解析 {url[:60]}...")

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
            cls = get_platform(self._platform)
            a = cls(config=PlatformConfig(
                name=self._platform, display_name=self._platform,
                domains=[], cookie=self._cm.get(self._platform)))
            try:
                raw_detail = await a.request_detail(links[0])
                return a.parse_detail(raw_detail) if raw_detail else None
            finally:
                await a.close()

        def _done(work):
            if not work:
                self._set_info("✗ 解析失败: 未获取到作品资料")
                return
            from shared.core import norm_work
            self._work = work
            self._norm_work = norm_work(work, self._platform)
            media = work.get("media_type") or ""
            n_img = 0
            imgs = work.get("image_urls")
            if isinstance(imgs, list):
                n_img = len(imgs)
            elif isinstance(imgs, str) and "http" in imgs:
                n_img = 1
            kind = (f"图集 {n_img} 张" if media == "images" else "视频")
            title = (work.get("title") or work.get("desc") or "")[:60]
            self._set_info(f"✓ [{kind}] {title}  (作者: {work.get('author_name', '?')})")

        self._run_task(_do(), _done, "解析预览", guard_key="preview")

    # ---------------- 功能执行 ----------------
    def action_execute(self, feature_id: str) -> None:
        if not self._platform:
            self._set_info("⚠ 请先选择平台")
            return
        ops = PlatformBus.get_ops(self._platform)
        feat = next((f for f in (ops.features if ops else [])
                     if f.id == feature_id), None)
        if feat and feat.need_url and not self._current_url:
            self._set_info(f"⚠ [{feat.name}] 需要先粘贴链接并解析 (Ctrl+P)")
            return
        self._run_feature(feature_id, None)

    def _run_feature(self, feature_id: str, selected: list | None) -> None:
        cookie = self._cm.get(self._platform)
        save_dir = VOLUME / self._platform
        save_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        async def _do():
            return await PlatformBus.run(
                self._platform, feature_id, self._current_url,
                cookie, save_dir,
                selected=selected, stop_event=self._stop_event)

        def _done(result):
            if result is None:
                return
            # 批量预览 → 勾选屏
            if result.preview == "batch" and result.data:
                self._open_batch_select(result.message, result.data, feature_id)
                return
            status = "✓" if result.success else "✗"
            n_files = len(result.files or [])
            msg = result.message
            if n_files:
                msg += f" (保存 {n_files} 个文件)"
            self._set_info(f"{status} {msg}")
            self._refresh_status()

        self._run_task(_do(), _done, f"功能 {feature_id}",
                       guard_key=f"feat:{feature_id}")

    def _open_batch_select(self, title: str, items: list,
                           feature_id: str) -> None:
        def _cb(selected):
            if selected:
                self._set_info(f"✓ 已勾选 {len(selected)} 项, 开始下载...")
                self._run_feature(feature_id, selected)
        self.push_screen(BatchSelectScreen(title, items), _cb)

    # ---------------- 系统 ----------------
    def action_open_login(self) -> None:
        if not self._platform:
            self._set_info("⚠ 请先选择平台")
            return
        try:
            ops = PlatformBus.get_ops(self._platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self.push_screen(LoginScreen(self._platform, hint), self._after_login)

    def _after_login(self, result) -> None:
        if result and result.get("cookie_changed"):
            self._refresh_status()
            self._set_info("✓ Cookie 已更新")

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._after_settings)

    def _after_settings(self, result) -> None:
        if result and result.get("settings_saved"):
            self._set_info("✓ 设置已保存")
            self._refresh_status()
