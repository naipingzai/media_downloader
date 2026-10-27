"""TUI — 终端原生页面, GUI 全部功能。

页面 (极简单列, 不模仿 GUI 排版):
  ┌────────────────────────────────────┐
  │ 平台: [抖音] [B站] [快手] [小红书]    │
  │ [链接输入             ] [解析预览]   │
  │ ▶ 作品: 标题/类型/统计              │
  │ ⬇下载作品 ⬇批量下载账号 🔴停止录制  │
  │ 作品操作: 获取链接/查看评论/下载封面  │
  │ 作者操作: 获取作品/关注/收藏/头像/主页│
  │ 📋 平台功能: (全部 FeatureMeta)      │
  │ [登录] [设置]                      │
  │ 💬 状态: ...                       │
  └────────────────────────────────────┘
功能与 GUI 完全一致: 解析/下载/批量/直播录制/合集/收藏夹/
  获取作品/关注列表/收藏列表/评论/头像/主页/链接/封面
列表结果用 DataTableScreen 表格展示。
"""
from __future__ import annotations

import asyncio

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
from .screens import (
    BatchSelectScreen, DataTableScreen, LoginScreen, SettingsScreen,
    TaskScreen,
)

APP_VERSION_LABEL = "TUI"



def fmt_count(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 100000000:
        return f"{n / 100000000:.1f}亿"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


class TuiApp(App):
    """MediaDownloader TUI — 终端页面 + GUI 全部功能。"""

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
    .act-row { height: 3; margin-bottom: 1; }
    .act-btn { margin: 0 1; height: 3; }
    #feat-label { text-style: bold; color: $accent; padding: 0 1; }
    #feat-scroll { height: auto; max-height: 16; margin-bottom: 1; }
    .menu-btn { width: 1fr; height: 3; margin: 0 1; }
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
        self._current_user: dict = {}
        self._task_guard: set = set()
        self._task_screen = None
        self._task_result_set = False
        self._stop_event = threading.Event()

    # ---------------- 布局 ----------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="plat-row"):
            yield Label("平台:", id="plat-label")
            for pid in PlatformBus.list_platforms():
                yield Button(_pn(pid), id=f"plat-{pid}", classes="plat-btn")
        with Horizontal(id="link-row"):
            yield Input(placeholder="粘贴作品链接/分享文本 → Ctrl+P 解析预览",
                        id="link-input")
            yield Button("解析预览", id="act-preview", variant="primary")
        yield Static("未解析 — 粘贴链接后按 [解析预览]", id="work-info")
        # 下载主操作
        with Horizontal(classes="act-row"):
            yield Button("⬇ 下载作品", id="act-dl", classes="act-btn",
                         variant="success")
            yield Button("⬇ 批量下载账号", id="act-account", classes="act-btn")
            yield Button("🔴 停止录制", id="act-stop", classes="act-btn",
                         variant="error")
        # 作品操作 (对应 GUI 作品操作组)
        with Horizontal(classes="act-row"):
            yield Button("🔗 获取链接", id="act-link", classes="act-btn")
            yield Button("💬 查看评论", id="act-comments", classes="act-btn")
            yield Button("🖼 下载封面", id="act-cover", classes="act-btn")
        # 作者操作 (对应 GUI 作者操作组)
        with Horizontal(classes="act-row"):
            yield Button("📄 获取作品", id="au-works", classes="act-btn")
            yield Button("👥 关注列表", id="au-follow", classes="act-btn")
            yield Button("⭐ 收藏列表", id="au-collect", classes="act-btn")
            yield Button("🖼 下载头像", id="au-avatar", classes="act-btn")
            yield Button("🌐 作者主页", id="au-home", classes="act-btn")
        # 平台功能 (全部 FeatureMeta, 预建按钮)
        yield Label("📋 平台功能", id="feat-label")
        with VerticalScroll(id="feat-scroll"):
            for i in range(self.MAX_FEATURES):
                b = Button("", id=f"feat-{i}", classes="menu-btn")
                b.feature_id = ""  # type: ignore[attr-defined]
                b.display = False
                yield b
        with Horizontal(classes="act-row"):
            yield Button("🔑 登录 (l)", id="sys-login", classes="act-btn")
            yield Button("⚙ 设置 (s)", id="sys-settings", classes="act-btn")
        yield Static("", id="status-line")
        yield Label("", id="footer-status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_menu()
        self._refresh_status()
        if "douyin" in PlatformBus.list_platforms():
            self._select_platform("douyin")

    # ---------------- 平台切换 (预建按钮+属性更新, 不闪退) ----------------
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
            if self._cm.get(pid):
                self._load_current_user()
        except Exception as e:
            self._set_info(f"⚠ 切换平台异常: {e}")

    def _refresh_menu(self) -> None:
        """更新平台功能按钮 (全部 FeatureMeta)。"""
        try:
            btns = list(self.query(".menu-btn"))
            feats = list(PlatformBus.get_features(self._platform)) \
                if self._platform else []
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

    def _set_info(self, msg: str) -> None:
        try:
            self.query_one("#status-line", Static).update(msg)
        except Exception:
            pass

    def _set_work(self, text: str) -> None:
        """更新作品信息框 (解析预览按钮下方)。"""
        try:
            self.query_one("#work-info", Static).update(text)
        except Exception:
            pass

    def _finish_task(self, ok: bool, msg: str) -> None:
        """结果写入状态行 + 任务弹窗。"""
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
                "act-link": self._act_copy_link,
                "act-comments": self._act_comments,
                "act-cover": self._act_download_cover,
                "au-works": self._act_fetch_works,
                "au-follow": self._act_follow_list,
                "au-collect": self._act_collect_list,
                "au-avatar": self._act_download_avatar,
                "au-home": self._act_open_home,
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
                  guard_key: str = "", popup: bool = True) -> None:
        if guard_key and guard_key in self._task_guard:
            self._set_info(f"⚠ [{name}] 已在执行中 (x 可停止)")
            coro.close()
            return
        if guard_key:
            self._task_guard.add(guard_key)
        # 任务弹窗 (与批量下载弹窗同风格)
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
        """任务日志 → 弹窗 (无弹窗时走状态行)。"""
        if self._task_screen:
            try:
                self._task_screen.append_log(str(msg))
                return
            except Exception:
                pass
        self._set_info(str(msg))

    def action_stop_task(self) -> None:
        self._stop_event.set()
        self._set_info("■ 已请求停止录制/任务")

    # ---------------- 基础辅助 ----------------
    def _adapter(self):
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        cls = get_platform(self._platform)
        return cls(config=PlatformConfig(
            name=self._platform, display_name=self._platform,
            domains=[], cookie=self._cm.get(self._platform)))

    async def _fetch_current_user(self) -> dict:
        """获取当前登录用户 (内部用)。"""
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
        """作品作者 sec_uid, 回退当前登录用户。"""
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
        self._finish_task(True, f"{title}: {len(rows)} 行 (Esc 关闭表格)")

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
            # 更新作品信息框 (解析按钮下方)
            self._set_work(
                f"[{kind}] {title[:90] or '未命名'}\n作者: {author}")
            self._finish_task(True, f"解析成功 [{kind}] {(title or '')[:50]}")

        self._run_task(_do(), _done, "解析预览", guard_key="preview")

    # ---------------- 功能执行 (平台 FeatureMeta) ----------------
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
                cookie, save_dir, on_log=self._task_log,
                selected=selected, stop_event=self._stop_event)

        def _done(result):
            if result is None:
                return
            for line in (result.log or [])[-20:]:
                self._task_log(line)
            if result.preview == "batch" and result.data:
                self._open_batch_select(result.message, result.data, feature_id)
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

    # ---------------- 作品操作 (对应 GUI 作品操作组) ----------------
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

    # ---------------- 作者操作 (对应 GUI 作者操作组) ----------------
    def _act_fetch_works(self) -> None:
        sec = self._sec_uid()
        if not sec:
            self._set_info("⚠ 未获取到作者 (先解析作品)")
            return
        self._set_info("▸ 获取作者所有作品...")

        async def _do():
            from shared.core import norm_work
            a = self._adapter()
            try:
                items = []
                cursor = "0"
                for page in range(10):
                    data = await a.fetch_user_posts(sec, count=20,
                                                    max_cursor=cursor)
                    if not data:
                        break
                    if isinstance(data, list):
                        items.extend(norm_work(w, self._platform) for w in data)
                        break
                    aws = data.get("aweme_list") or data.get("data") or []
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
            self._open_table("作者所有作品", ["标题", "作者", "时长", "点赞"],
                             [[w.get("title", "")[:50], w.get("author_name", ""),
                               f"{w.get('duration', 0)}s",
                               fmt_count(w.get("digg_count"))]
                              for w in (items or [])])

        self._run_task(_do(), _done, "作者作品", guard_key="works")

    def _act_follow_list(self) -> None:
        self._set_info("▸ 拉取关注列表...")

        async def _do():
            from shared.core import norm_user
            u = await self._fetch_current_user()
            sec = u.get("sec_user_id") or u.get("sec_uid") or ""
            if not sec:
                return None
            a = self._adapter()
            try:
                users = []
                max_time = "0"
                for _ in range(3):
                    data = await a.fetch_user_following(sec, count=20,
                                                        max_time=max_time)
                    if not data:
                        break
                    if isinstance(data, list):
                        users.extend(norm_user(x, self._platform) for x in data)
                        break
                    fl = (data.get("followings") or data.get("follow_list")
                          or (data.get("data") or {}).get("followings") or [])
                    if not fl:
                        break
                    users.extend(norm_user(x, self._platform) for x in fl)
                    if not data.get("has_more"):
                        break
                    max_time = str(data.get("max_time") or "0")
                    if max_time == "0":
                        break
                return users
            finally:
                await a.close()

        def _done(users):
            if users is None:
                self._set_info("⚠ 未获取到当前登录用户 (需登录 Cookie)")
                return
            self._open_table("关注列表", ["昵称", "签名", "粉丝"],
                             [[u.get("nickname", ""),
                               (u.get("signature") or "")[:30],
                               fmt_count(u.get("follower_count"))]
                              for u in users])

        self._run_task(_do(), _done, "关注列表", guard_key="follow")

    def _act_collect_list(self) -> None:
        self._set_info("▸ 拉取收藏列表...")

        async def _do():
            from shared.core import norm_work
            a = self._adapter()
            try:
                items = []
                cursor = "0"
                for _ in range(5):
                    data = await a.fetch_collection(cursor=cursor, count=20)
                    if not data:
                        break
                    if isinstance(data, list):
                        items.extend(norm_work(w, self._platform) for w in data)
                        break
                    aws = (data.get("aweme_list")
                           or (data.get("data") or {}).get("aweme_list") or [])
                    if not aws:
                        break
                    items.extend(norm_work(w, self._platform) for w in aws)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("cursor") or "0")
                    if cursor == "0":
                        break
                return items
            finally:
                await a.close()

        def _done(items):
            self._open_table("收藏列表", ["标题", "作者", "点赞"],
                             [[w.get("title", "")[:50], w.get("author_name", ""),
                               fmt_count(w.get("digg_count"))]
                              for w in (items or [])])

        self._run_task(_do(), _done, "收藏列表", guard_key="collect")

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

    def _act_open_home(self) -> None:
        sec = self._sec_uid()
        if not sec:
            self._set_info("⚠ 无作者信息 (先解析作品)")
            return
        p = (self._current_user.get("platform")
             or self._work.get("platform") or self._platform)
        home = {
            "bilibili": f"https://space.bilibili.com/{sec}",
            "kuaishou": f"https://www.kuaishou.com/profile/{sec}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{sec}",
        }.get(p, f"https://www.douyin.com/user/{sec}")
        self._set_info(f"✓ 作者主页: {home}")

    # ---------------- 当前用户 ----------------
    def _load_current_user(self) -> None:
        if not self._cm.get(self._platform):
            return

        async def _do():
            return await self._fetch_current_user()

        def _done(u):
            if u:
                self._set_info(f"✓ 当前用户: {u.get('nickname', '?')}")

        self._run_task(_do(), _done, "当前用户", guard_key="user",
                       popup=False)

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
            self._current_user = {}
            self._refresh_status()
            self._set_info("✓ Cookie 已更新")
            self._load_current_user()

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._after_settings)

    def _after_settings(self, result) -> None:
        if result and result.get("settings_saved"):
            self._set_info("✓ 设置已保存")
            self._refresh_status()
