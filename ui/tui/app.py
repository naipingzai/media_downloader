"""TUI — MediaDownloader 终端界面 (Textual)。

布局 (左右分栏, 类 GUI 双栏):
  ┌──────────────┬──────────────────────────────────┐
  │ 平台          │ 链接 [________________] [解析预览] │
  │  ▸ 抖音       │ ┌ 作品信息 ─────────────────────┐ │
  │  ▸ B站        │ │ 标题 / 作者 / 类型 / 数据      │ │
  │  ▸ 快手       │ └───────────────────────────────┘ │
  │ ────────────  │ ┌ 功能按钮 (按平台动态生成) ────┐ │
  │ 功能 (动态)    │ │ [下载作品] [批量账号] [评论]…  │ │
  │  ▸ 下载作品    │ └───────────────────────────────┘ │
  │  ▸ 批量账号    │ ┌ 执行日志 ─────────────────────┐ │
  │  …            │ │ 实时滚动日志                   │ │
  │ 操作          │ └───────────────────────────────┘ │
  │  [登录] [设置] │                                  │
  └──────────────┴──────────────────────────────────┘
  模态屏: 登录 / 设置 / 批量勾选 / 数据表 / 任务进度
快捷键: q 退出 | l 登录 | s 设置 | p 解析 | x 停止 | tab 焦点切换
"""
from __future__ import annotations

import asyncio
import re
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem, ListView, Log, Static,
)

from shared.core import (
    PROJECT_NAME, VOLUME, CookieManager, PlatformBus,
    platform_name as _pn,
)
from platforms import load_all_platforms
from shared.core.format import format_count as fmt_count
from .screens import (
    BatchSelectScreen, DataTableScreen, LoginScreen, SettingsScreen,
    TaskScreen,
)


class TuiApp(App):
    """MediaDownloader TUI — 双栏终端界面。"""

    TITLE = PROJECT_NAME
    SUB_TITLE = "TUI"

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("l", "open_login", "登录"),
        Binding("s", "open_settings", "设置"),
        Binding("p", "preview", "解析"),
        Binding("x", "stop_task", "停止"),
    ]

    CSS = """
    #body { height: 1fr; }
    #sidebar { width: 30; min-width: 24; border-right: round $primary;
               padding: 0 1; }
    #main { width: 1fr; padding: 0 1; }
    .side-title { text-style: bold; color: $accent; margin-top: 1; }
    #plat-list { height: auto; max-height: 8; }
    #plat-list > ListItem { padding: 0 1; }
    #feat-list { height: 1fr; }
    .side-btn { width: 1fr; height: 3; margin: 0; }
    #link-row { height: 3; margin-bottom: 1; }
    #link-input { width: 1fr; }
    #work-info { height: auto; margin-bottom: 1;
                 padding: 0 1; border: round $panel; color: $text; }
    #log-box { height: 1fr; border: round $panel; padding: 0 1;
               scrollbar-size: 0 0; }
    #status-line { height: auto; color: $text-muted; padding: 0 1; }
    """

    def __init__(self):
        super().__init__()
        load_all_platforms()
        self._cm = CookieManager()
        self._platform = ""
        self._current_url = ""
        self._work: dict = {}
        self._norm_work: dict = {}
        self._current_user: dict = {}
        self._task_guard: set = set()
        self._task_screen = None
        self._task_result_set = False
        self._stop_event = threading.Event()

    # ---------------- 布局 ----------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            # ---- 左栏: 平台 + 功能菜单 + 系统操作 ----
            with Vertical(id="sidebar"):
                yield Label("平台", classes="side-title")
                yield ListView(id="plat-list")
                yield Label("功能", classes="side-title")
                yield ListView(id="feat-list")
                yield Label("系统", classes="side-title")
                yield Button("🔑 登录 (l)", id="sys-login",
                             classes="side-btn")
                yield Button("⚙ 设置 (s)", id="sys-settings",
                             classes="side-btn")
                yield Button("📜 下载记录", id="sys-history",
                             classes="side-btn")
                yield Button("🔴 停止任务 (x)", id="sys-stop",
                             classes="side-btn", variant="error")
            # ---- 右栏: 链接 + 作品信息 + 日志 ----
            with Vertical(id="main"):
                with Horizontal(id="link-row"):
                    yield Input(
                        placeholder="粘贴作品链接/分享文本 → Enter 或 p 解析",
                        id="link-input")
                    yield Button("解析预览", id="act-preview",
                                 variant="primary")
                yield Static("未解析 — 粘贴链接后按 [解析预览]",
                             id="work-info")
                yield Label("执行日志", classes="side-title")
                yield Log(id="log-box")
                yield Static("", id="status-line")
        yield Footer()

    def on_mount(self) -> None:
        # 平台列表
        plat_list = self.query_one("#plat-list", ListView)
        for pid in PlatformBus.list_platforms():
            plat_list.append(ListItem(Label(f"▸ {_pn(pid)}"),
                                      name=pid))
        self._refresh_menu()
        self._refresh_status()
        if "douyin" in PlatformBus.list_platforms():
            self._select_platform("douyin")

    # ---------------- 左栏交互 ----------------

    def _select_platform(self, pid: str) -> None:
        try:
            self._platform = pid
            self._work = {}
            self._norm_work = {}
            self._current_user = {}
            self._refresh_menu()
            self._set_work(f"已切换到 {_pn(pid)} — 粘贴链接后按 [解析预览]")
            self._refresh_status()
            if self._cm.get(pid):
                self._load_current_user()
        except Exception as e:
            self._set_info(f"⚠ 切换平台异常: {e}")

    def _refresh_menu(self) -> None:
        """功能菜单按当前平台 FeatureMeta 重建。"""
        try:
            fl = self.query_one("#feat-list", ListView)
            fl.clear()
            for f in (PlatformBus.get_features(self._platform)
                      if self._platform else []):
                item = ListItem(Label(f"▸ {f.name}"))
                item.feature_id = f.id          # type: ignore[attr-defined]
                item.need_url = f.need_url       # type: ignore[attr-defined]
                fl.append(item)
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """平台列表回车=切换平台; 功能列表回车=执行功能。"""
        lst = event.control
        if lst.id == "plat-list":
            pids = PlatformBus.list_platforms()
            if lst.index is not None and 0 <= lst.index < len(pids):
                pid = pids[lst.index]
                if pid != self._platform:
                    self._select_platform(pid)
        elif lst.id == "feat-list" and event.item is not None:
            fid = getattr(event.item, "feature_id", "")
            if fid:
                self.action_execute(fid)

    # ---------------- 状态渲染 ----------------

    def _refresh_status(self) -> None:
        try:
            parts = []
            if not self._platform:
                parts.append("未选择平台")
            else:
                cookie = self._cm.get(self._platform)
                name = _pn(self._platform)
                if cookie and cookie.strip():
                    parts.append(f"{name}: ✓ Cookie 已配置")
                else:
                    parts.append(f"{name}: ✗ 未登录 (l 登录)")
            parts.append(f"目录: {VOLUME}")
            self.query_one("#status-line", Static).update(
                "  |  ".join(parts))
        except Exception:
            pass

    def _set_info(self, msg: str) -> None:
        try:
            self.query_one("#status-line", Static).update(msg)
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        try:
            self.query_one("#log-box", Log).write(str(msg))
        except Exception:
            pass

    def _set_work(self, text: str) -> None:
        try:
            self.query_one("#work-info", Static).update(text)
        except Exception:
            pass

    def _finish_task(self, ok: bool, msg: str) -> None:
        self._task_result_set = True
        if self._task_screen:
            try:
                self._task_screen.set_result(ok, msg)
            except Exception:
                pass
        self._set_info(("✓ " if ok else "✗ ") + str(msg))

    # ---------------- 事件 ----------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            bid = event.button.id or ""
            if bid == "act-preview":
                self.action_preview()
            elif bid == "sys-login":
                self.action_open_login()
            elif bid == "sys-settings":
                self.action_open_settings()
            elif bid == "sys-history":
                self.action_open_history()
            elif bid == "sys-stop":
                self.action_stop_task()
        except Exception as e:
            self._set_info(f"⚠ 异常: {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "link-input":
            self.action_preview()

    # ---------------- 后台任务 ----------------

    def _run_task(self, coro, on_done=None, name="task",
                  guard_key: str = "", popup: bool = True) -> None:
        if guard_key and guard_key in self._task_guard:
            self._set_info(f"⚠ [{name}] 已在执行中 (x 可停止)")
            coro.close()
            return
        if guard_key:
            self._task_guard.add(guard_key)
        if popup:
            try:
                scr = TaskScreen(name)
                self._task_screen = scr
                self._task_result_set = False

                def _clear(_r=None, _s=scr):
                    if self._task_screen is _s:
                        self._task_screen = None
                self.push_screen(scr, _clear)
            except Exception:
                self._task_screen = None

        async def _wrapped():
            ok, msg = True, "完成"
            try:
                result = await coro
            except Exception as e:
                ok, msg = False, f"{type(e).__name__}: {e}"
                self._set_info(f"✗ {name} 失败: {msg}")
                result = None
            finally:
                if guard_key:
                    self._task_guard.discard(guard_key)
            if on_done:
                try:
                    on_done(result)
                except Exception as e:
                    ok, msg = False, f"回调异常: {e}"
                    self._set_info(f"✗ 回调异常: {e}")
            if self._task_screen and not self._task_result_set:
                try:
                    self._task_screen.set_result(ok, msg)
                except Exception:
                    pass

        self.run_worker(_wrapped(), exclusive=False, group="task",
                        description=name)

    def _task_log(self, msg: str) -> None:
        self._log(str(msg))

    def action_stop_task(self) -> None:
        self._stop_event.set()
        self._set_info("■ 已请求停止任务")

    # ---------------- 基础辅助 ----------------

    def _adapter(self):
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        cls = get_platform(self._platform)
        return cls(config=PlatformConfig(
            name=self._platform, display_name=self._platform,
            domains=[], cookie=self._cm.get(self._platform)))

    async def _fetch_current_user(self) -> dict:
        if self._current_user:
            return self._current_user
        a = self._adapter()
        try:
            u = None
            if hasattr(a, "fetch_current_user"):
                u = await a.fetch_current_user()
            if u:
                self._current_user = u
            return u or {}
        finally:
            await a.close()

    def _sec_uid(self) -> str:
        for src in (self._work, self._current_user):
            sec = (src.get("sec_user_id") or src.get("sec_uid")
                   or src.get("user_id") or "")
            if sec:
                return sec
        return ""

    def _open_table(self, title: str, headers: list, rows: list) -> None:
        if not rows:
            self._finish_task(False, f"{title}: 没有数据")
            return
        self.push_screen(DataTableScreen(title, headers, rows))
        self._finish_task(True, f"{title}: {len(rows)} 行 (Esc 关闭)")

    # ---------------- 解析预览 ----------------

    def action_preview(self) -> None:
        if not self._platform:
            self._set_info("⚠ 请先在左栏选择平台")
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
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, self._platform)
            finally:
                await client.close()
            if not links:
                return None
            a = self._adapter()
            try:
                raw_detail = await a.request_detail(links[0])
                return a.parse_detail(raw_detail) if raw_detail else None
            finally:
                await a.close()

        def _done(work):
            if not work:
                self._finish_task(False, "解析失败: 未获取到作品资料")
                return
            from shared.core import norm_work
            self._work = work
            self._norm_work = norm_work(work, self._platform)
            media = work.get("media_type") or ""
            imgs = work.get("image_urls")
            n_img = (len(imgs) if isinstance(imgs, list)
                     else 1 if isinstance(imgs, str) and "http" in imgs else 0)
            kind = (f"图集 {n_img} 张" if media == "images" else "视频")
            title = (work.get("title") or work.get("desc") or "").strip()
            author = work.get("author_name") or "?"
            digg = fmt_count(self._norm_work.get("digg_count", 0))
            self._set_work(
                f"❖ {title[:70] or '未命名'}\n"
                f"作者: {author}   类型: {kind}   点赞: {digg}")
            self._finish_task(True, f"解析成功 [{kind}] {(title or '')[:50]}")

        self._run_task(_do(), _done, "解析预览", guard_key="preview")

    # ---------------- 功能执行 (平台 FeatureMeta) ----------------

    def action_execute(self, feature_id: str) -> None:
        if not self._platform:
            self._set_info("⚠ 请先在左栏选择平台")
            return
        ops = PlatformBus.get_ops(self._platform)
        feat = next((f for f in (ops.features if ops else [])
                     if f.id == feature_id), None)
        if feat and feat.need_url and not self._current_url:
            self._set_info(f"⚠ [{feat.name}] 需要先粘贴链接并解析 (p)")
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
                cookie, save_dir, on_log=self._task_log,
                selected=selected, stop_event=self._stop_event)

        def _done(result):
            if result is None:
                return
            for line in (result.log or [])[-20:]:
                self._log(line)
            if result.preview == "batch" and result.data:
                self._open_batch_select(result.message, result.data,
                                        feature_id)
                return
            msg = result.message
            if result.files:
                msg += f" (保存 {len(result.files)} 个文件)"
            _meta = PlatformBus.get_feature(self._platform, feature_id)
            if (result.data and _meta and _meta.emits_work_info
                    and not result.preview):
                from shared.core import norm_work
                d0 = result.data[0]
                self._work = d0
                self._norm_work = norm_work(d0, self._platform)
                title = (d0.get("title") or "")[:60]
                self._set_work(f"[已下载] {title or '作品'}")
            self._finish_task(result.success, msg)
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

    # ---------------- 数据辅助 (评论/封面/头像/主页) ----------------

    def _act_copy_link(self) -> None:
        url = (self._work.get("share_url")
               or self._norm_work.get("share_url") or "")
        if url:
            self._set_info(f"✓ 作品链接: {url}")
        else:
            self._set_info("⚠ 无作品链接 (先解析预览)")

    def _act_comments(self) -> None:
        wid = str(self._work.get("work_id") or "")
        if not wid:
            self._set_info("⚠ 无作品ID (先解析预览)")
            return
        self._set_info(f"▸ 获取评论: {wid}...")

        async def _do():
            from shared.core import norm_comment
            a = self._adapter()
            try:
                data = await a.fetch_comments(wid)
                if isinstance(data, dict):
                    data = data.get("comments") or data.get("data") or []
                return [norm_comment(c) for c in (data or [])
                        if isinstance(c, dict)]
            finally:
                await a.close()

        def _done(items):
            items = [c for c in (items or []) if c.get("content")]
            self._open_table("评论列表", ["用户", "内容"],
                             [[c.get("nickname", "—"), c.get("content", "")]
                              for c in items])

        self._run_task(_do(), _done, "评论", guard_key="comments")

    def _act_download_cover(self) -> None:
        url = (self._work.get("cover_url")
               or self._norm_work.get("cover_url") or "")
        if not url:
            self._set_info("⚠ 无封面地址 (先解析预览)")
            return
        self._download_image(url, "covers", "封面")

    def _download_image(self, url: str, subdir: str, prefix: str) -> None:
        async def _do():
            import time
            from curl_cffi.requests import get as _get
            r = await asyncio.to_thread(_get, url, timeout=15,
                                        impersonate="chrome146")
            d = VOLUME / (self._platform or "common") / subdir
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{prefix}_{int(time.time())}.jpg"
            path.write_bytes(bytes(r.content))
            return str(path)

        def _done(path):
            if path:
                self._finish_task(True, f"{prefix}已保存: {path}")
            else:
                self._finish_task(False, f"{prefix}下载失败")

        self._run_task(_do(), _done, f"{prefix}下载", guard_key=prefix)

    def _act_download_avatar(self) -> None:
        self._set_info("▸ 获取用户头像...")

        async def _do():
            u = await self._fetch_current_user()
            return u.get("avatar") or ""

        def _done(url):
            if not url:
                self._set_info("⚠ 无头像地址 (需登录 Cookie)")
                return
            self._download_image(url, "avatars", "头像")

        self._run_task(_do(), _done, "头像地址", guard_key="avatar-addr",
                       popup=False)

    # ---------------- 当前用户 ----------------

    def _load_current_user(self) -> None:
        if not self._cm.get(self._platform):
            return

        async def _do():
            return await self._fetch_current_user()

        def _done(u):
            if u:
                self._log(f"✓ 当前用户: {u.get('nickname', '?')}")

        self._run_task(_do(), _done, "当前用户", guard_key="user",
                       popup=False)

    # ---------------- 系统 ----------------

    def action_open_login(self) -> None:
        if not self._platform:
            self._set_info("⚠ 请先在左栏选择平台")
            return
        try:
            ops = PlatformBus.get_ops(self._platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self.push_screen(LoginScreen(self._platform, hint), self._after_login)

    def _after_login(self, result) -> None:
        if result and result.get("cookie_changed"):
            self._current_user = {}
            self._refresh_status()
            self._set_info("✓ Cookie 已更新")
            self._load_current_user()

    def action_open_history(self) -> None:
        """打开下载记录 (GUI/TUI 共用 Volume/history.jsonl)。"""
        from shared.core.download_history import get_history
        rows = get_history().load(limit=300)
        if not rows:
            self._set_info("⚠ 暂无下载记录")
            return
        headers = ["时间", "平台", "作品介绍", "作者", "发布日期", "链接"]
        table_rows = []
        for r in rows:
            log_tail = "; ".join((r.get("log") or [])[-2:])
            link = (r.get("share_url") or "")[:40]
            table_rows.append([
                r.get("downloaded_at", ""),
                r.get("platform", ""),
                (r.get("title") or "")[:36],
                r.get("author_name", ""),
                r.get("publish_date", ""),
                link + (f" | {log_tail}" if log_tail else ""),
            ])
        self.push_screen(DataTableScreen("下载记录", headers, table_rows))
        self._log(f"✓ 下载记录: {len(rows)} 条 (最新在前)")

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._after_settings)

    def _after_settings(self, result) -> None:
        if result and result.get("settings_saved"):
            self._set_info("✓ 设置已保存")
            self._refresh_status()
