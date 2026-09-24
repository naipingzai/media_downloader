"""主窗口 —— 重构 UI (保留原版布局)。

布局:
  ┌──────┬────────────────────────────────────────────────┐
  │      │  链接栏 (顶)                                     │
  │  侧  ├─────────────────────────────────────────────────┤
  │  栏  │  作者资料卡 (顶部)                                │
  │      ├─────────────────────────────────────────────────┤
  │ 每行 │  │ 作品资料区 (多页内嵌 QTabWidget)              │
  │ 加框 │  │  ├─ 作品资料 (默认, 不可关)                  │
  │      │  │  ├─ 作品网格 / 用户列表 / 数据表格 / 登录    │
  │      │  │  └─ 设置 (可关闭页签)                       │
  │      ├─────────────────────────────────────────────────┤
  │      │  功能面板                                         │
  │      ├─────────────────────────────────────────────────┤
  │      │  可折叠日志条                                     │
  └──────┴────────────────────────────────────────────────┘
                                底部状态栏: Cookie + 版本 + FFmpeg
"""
import asyncio
import subprocess
import sys
from PySide6.QtCore import QObject, Qt, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
    QApplication,
)
from shared.core import (
    PROJECT_NAME, VOLUME, __VERSION__, CookieManager, PlatformBus,
    platform_name as _pn, FFmpegManager, LoginBus, ConfigManager, norm_user,
)
from .threads.worker import FeatureWorker
from .widgets.feature_panel import FeaturePanel
from .widgets.video_info import VideoInfoWidget
from .widgets.author_profile_panel import AuthorProfilePanel
from .widgets.log_panel import LogPanel
from .widgets.section_panel import SectionPanel
from .widgets.embedded_tabs import EmbeddedTabs
from .pages.work_grid_page import WorkGridPage
from .pages.users_page import UsersPage
from .pages.data_table_page import DataTablePage
from .pages.login_page import LoginPage
from .pages.settings_page import SettingsPage
from .resources import theme as _theme


APP_VERSION_LABEL = "MediaDownloader V1.0 Beta"


# ===================== 后台任务 =====================

class _UserFetchSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str, str)


class _UserFetchTask(QRunnable):
    """后台拉取当前登录用户 (异步, 带日志 + 15s 超时)。"""

    def __init__(self, cookie: str, platform: str = "douyin"):
        super().__init__()
        self.cookie = cookie
        self.platform = platform or "douyin"
        self.signals = _UserFetchSignals()
        self.setAutoDelete(True)

    def _log(self, msg: str, color: str = "#94a3b8"):
        try:
            self.signals.log.emit(msg, color)
        except RuntimeError:
            pass

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._fetch())
            finally:
                loop.close()
            try:
                self.signals.done.emit(result)
            except RuntimeError:
                pass
        except asyncio.TimeoutError:
            self._log("✗ 请求超时 (15s)", "#f87171")
            try:
                self.signals.failed.emit("请求超时 (15s)")
            except RuntimeError:
                pass
        except Exception as e:
            import traceback
            self._log(f"✗ 异常: {type(e).__name__}: {e}", "#f87171")
            self._log(f"  {traceback.format_exc()[-300:]}", "#64748b")
            try:
                self.signals.failed.emit(f"{type(e).__name__}: {e}")
            except RuntimeError:
                pass

    async def _fetch(self):
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        cls = get_platform(self.platform)
        if not cls:
            self._log(f"✗ 平台 {self.platform} 适配器未找到", "#f87171")
            return None
        a = cls(config=PlatformConfig(
            name=self.platform, display_name=self.platform,
            domains=[], cookie=self.cookie))
        try:
            if hasattr(a, "fetch_current_user"):
                try:
                    u = await asyncio.wait_for(a.fetch_current_user(), timeout=15)
                    if u:
                        await a.close()
                        return u
                except Exception as e:
                    self._log(f"  fetch_current_user 失败: {e}", "#f59e0b")
            if self.platform == "douyin":
                return await self._fetch_douyin(a)
            await a.close()
            return None
        except Exception:
            await a.close()
            raise

    async def _fetch_douyin(self, a):
        try:
            for url, params in [
                ("https://www.douyin.com/aweme/v1/web/user/profile/self/", {}),
                ("https://www.douyin.com/passport/web/account/info/", {}),
            ]:
                resp = await asyncio.wait_for(a._signed_get(url, params), timeout=15)
                if not isinstance(resp, dict):
                    continue
                if resp.get("status_code") == 0 and (resp.get("data") or resp.get("user")):
                    return self._norm(resp)
            return None
        finally:
            await a.close()

    @staticmethod
    def _norm(resp: dict) -> dict:
        u = (resp.get("user") or resp.get("user_info")
             or (resp.get("data") or {}).get("user")
             or (resp.get("data") or {}).get("user_info")
             or resp.get("data") or resp)
        if not isinstance(u, dict):
            return {}
        avatar = u.get("avatar_larger") or u.get("avatar_medium") or u.get("avatar_thumb") or ""
        urls = avatar.get("url_list") if isinstance(avatar, dict) else []
        return {
            "user_id": u.get("uid") or u.get("user_id") or u.get("id", ""),
            "sec_user_id": u.get("sec_uid") or u.get("sec_user_id", ""),
            "nickname": u.get("nickname") or u.get("nick_name", ""),
            "signature": u.get("signature") or u.get("desc", ""),
            "avatar": urls[0] if urls else "",
            "follower_count": u.get("follower_count") or 0,
            "following_count": u.get("following_count") or 0,
            "total_favorited": u.get("total_favorited") or 0,
            "aweme_count": u.get("aweme_count") or 0,
        }


class _AuthorFetchSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str, str)


class _AuthorFetchTask(QRunnable):
    """后台拉取: works / collection / comments / following。"""

    def __init__(self, kind: str, sec_uid: str, cookie: str,
                 platform: str = "douyin"):
        super().__init__()
        self.kind = kind
        self.sec_uid = sec_uid
        self.cookie = cookie
        self.platform = platform or "douyin"
        self.signals = _AuthorFetchSignals()
        self.setAutoDelete(True)

    def _log(self, msg: str, color: str = "#94a3b8"):
        try:
            self.signals.log.emit(msg, color)
        except RuntimeError:
            pass

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._fetch())
            finally:
                loop.close()
            try:
                self.signals.done.emit(result or [])
            except RuntimeError:
                pass
        except Exception as e:
            self._log(f"✗ 拉取失败: {e}", "#f87171")
            try:
                self.signals.failed.emit(str(e))
            except RuntimeError:
                pass

    async def _fetch(self):
        from shared.core.adapter import PlatformConfig, norm_work, norm_user, norm_comment
        from platforms import get_platform
        cls = get_platform(self.platform)
        if not cls:
            return []
        a = cls(config=PlatformConfig(
            name=self.platform, display_name=self.platform,
            domains=[], cookie=self.cookie))
        try:
            if self.kind == "works":
                return await self._fetch_works(a, norm_work)
            if self.kind == "following":
                return await self._fetch_following(a, norm_user)
            if self.kind == "collection":
                return await self._fetch_collection(a, norm_work)
            if self.kind == "comments":
                return await self._fetch_comments(a, norm_comment)
            return []
        finally:
            await a.close()

    async def _fetch_comments(self, a, norm_comment) -> list:
        if not hasattr(a, "fetch_comments"):
            return []
        data = await a.fetch_comments(self.sec_uid)
        if isinstance(data, dict):
            data = data.get("comments") or data.get("data") or []
        if isinstance(data, list):
            return [c for c in (norm_comment(x) for x in data if isinstance(x, dict))
                    if c.get("content")]
        return []

    async def _fetch_works(self, a, norm_work) -> list:
        items = []
        cursor = "0"
        for page in range(5):
            self._log(f"  ▸ 拉取作品 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_user_posts(self.sec_uid, count=20, max_cursor=cursor)
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = data.get("aweme_list") or data.get("data") or []
            if isinstance(awemes, dict):
                awemes = awemes.get("aweme_list") or []
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("max_cursor") or "0")
            if cursor == "0":
                break
        self._log(f"✓ 共拉取 {len(items)} 个作品", "#22c55e")
        return items

    async def _fetch_following(self, a, norm_user) -> list:
        users = []
        max_time = "0"
        for page in range(3):
            self._log(f"  ▸ 拉取关注列表 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_user_following(self.sec_uid, count=20, max_time=max_time)
            if not data:
                break
            if isinstance(data, list):
                users.extend(norm_user(u, self.platform) for u in data)
                break
            fl = data.get("followings") or data.get("follow_list") or []
            if not fl:
                fl = (data.get("data") or {}).get("followings") or []
            if not fl:
                break
            users.extend(norm_user(u, self.platform) for u in fl)
            if not data.get("has_more"):
                break
            max_time = str(data.get("max_time") or "0")
            if max_time == "0":
                break
        self._log(f"✓ 共拉取 {len(users)} 个关注", "#22c55e")
        return users

    async def _fetch_collection(self, a, norm_work) -> list:
        items = []
        cursor = "0"
        for page in range(3):
            self._log(f"  ▸ 拉取收藏 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_collection(cursor=cursor, count=20)
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = data.get("aweme_list") or []
            if not awemes:
                awemes = (data.get("data") or {}).get("aweme_list") or []
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("cursor") or "0")
            if cursor == "0":
                break
        self._log(f"✓ 共拉取 {len(items)} 个收藏作品", "#22c55e")
        return items


# ===================== 主窗口 =====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROJECT_NAME)
        self.setMinimumSize(1180, 760)
        self.resize(1380, 900)
        self.menuBar().setVisible(False)
        PlatformBus  # force import (side effect 注册平台)
        from platforms import load_all_platforms
        load_all_platforms()
        self._cm = CookieManager()
        self._current_platform = ""
        self._current_url = ""
        self._current_user_profile = None
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(2)
        self._setup_pages()        # 先建可复用页 (login/settings 单例)
        self._setup_status_bar()
        self._setup_ui()           # 再建主 UI (含 EmbeddedTabs)

    # ---------------- 可复用页 ----------------
    def _setup_pages(self):
        self._settings_page = SettingsPage()
        self._settings_page.font_changed.connect(self._apply_font_size)
        self._settings_page.settings_saved.connect(self._on_settings_saved)
        self._login_page = LoginPage()
        self._login_page.cookie_changed.connect(self._refresh_cookie_status)

    # ---------------- 主 UI (单一垂直列, 不再左右分栏) ----------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        shell.addWidget(self._build_sidebar())

        # 主区: 单一垂直布局
        right = QWidget()
        v = QVBoxLayout(right)
        v.setContentsMargins(10, 10, 10, 8)
        v.setSpacing(8)

        # ---- 各区域固定高度, 不允许拉伸 (位置全部锁定) ----

        # 1) 链接栏 (固定高 56)
        sec_link = self._build_link_panel()
        v.addWidget(sec_link)

        # 2) 作者资料卡 (固定高 140)
        sec_author = self._build_author_panel()
        v.addWidget(sec_author)

        # 3) 作品资料区 (多页内嵌) —— 固定高, 不随窗口伸缩
        sec_video = self._build_video_panel()
        v.addWidget(sec_video, 1)        # 占剩余空间 (动态区域)

        # 4) 功能面板 (固定高 200)
        sec_feat = self._build_feature_section()
        v.addWidget(sec_feat)

        # 5) 静态日志条 (固定高 140, 不可展开)
        sec_log = self._build_log_section()
        v.addWidget(sec_log)

        shell.addWidget(right)

        if "douyin" in PlatformBus.list_platforms():
            self._select_platform("douyin")

    # ---------------- 各区域 (固定高度构造) ----------------
    def _build_link_panel(self) -> SectionPanel:
        link_bar = QFrame()
        link_bar.setObjectName("LinkBar")
        link_bar.setFixedHeight(48)
        link_bar.setStyleSheet(
            "#LinkBar { background: transparent; border: none; }")
        h = QHBoxLayout(link_bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "粘贴作品链接 (抖音/快手/小红书/B站) → 点击解析预览")
        self._url_input.setObjectName("LinkInput")
        self._url_input.textChanged.connect(self._on_url_changed)
        h.addWidget(self._url_input, 1)
        preview_btn = QPushButton("解析预览")
        preview_btn.setObjectName("PrimaryButton")
        preview_btn.setCursor(Qt.PointingHandCursor)
        preview_btn.clicked.connect(self._on_preview)
        h.addWidget(preview_btn)
        sec = SectionPanel("链接")
        sec.addWidget(link_bar)
        sec.setFixedHeight(86)        # 标题 + 输入框高度
        return sec

    def _build_author_panel(self) -> SectionPanel:
        self._author_panel = AuthorProfilePanel()
        self._author_panel.fetch_works_clicked.connect(self._on_fetch_works)
        self._author_panel.follow_list_clicked.connect(self._on_follow_list)
        self._author_panel.collect_list_clicked.connect(self._on_collect_list)
        self._author_panel.download_avatar_clicked.connect(self._on_download_avatar)
        self._author_panel.open_home_clicked.connect(self._on_open_home)
        sec = SectionPanel("作者资料")
        sec.addWidget(self._author_panel)
        sec.setFixedHeight(160)
        return sec

    def _build_video_panel(self) -> SectionPanel:
        self._video_info = VideoInfoWidget()
        # 锁死高度 · 上下滚动交给内部 ScrollArea
        self._video_info.setFixedHeight(360)
        self._tabs = EmbeddedTabs(self._video_info, default_title="作品资料")
        sec = SectionPanel("作品资料")
        sec.addWidget(self._tabs)
        sec.setFixedHeight(400)        # 标题 + 4px padding + 内容
        return sec

    def _build_feature_section(self) -> SectionPanel:
        self._feature_panel = self._build_feature_panel_inner()
        feat_scroll = QScrollArea()
        feat_scroll.setWidgetResizable(True)
        feat_scroll.setFrameShape(QScrollArea.NoFrame)
        feat_scroll.setWidget(self._feature_panel)
        sec = SectionPanel("功能")
        sec.addWidget(feat_scroll)
        sec.setFixedHeight(200)
        return sec

    def _build_log_section(self) -> SectionPanel:
        self._log = LogPanel()
        sec = SectionPanel("执行日志")
        sec.addWidget(self._log)
        sec.setFixedHeight(180)
        return sec

    def _build_feature_panel_inner(self) -> FeaturePanel:
        def _copy_work_link():
            w = self._video_info.work
            self._on_copy_link(w.get("share_url") or w.get("video_url", ""))

        def _show_comments():
            self._on_show_comments(str(self._video_info.work.get("work_id", "")))

        def _download_cover():
            self._on_download_cover(self._video_info.cover_url)

        def _dl_avatar():
            self._on_download_avatar(self._author_panel.profile.get("avatar", ""))

        def _open_home():
            prof = self._author_panel.profile
            sec = (prof.get("sec_user_id") or prof.get("sec_uid")
                   or prof.get("user_id") or "")
            p = prof.get("platform", "") or self._current_platform
            home = ""
            if sec:
                if p == "bilibili":
                    home = f"https://space.bilibili.com/{sec}"
                elif p == "kuaishou":
                    home = f"https://www.kuaishou.com/profile/{sec}"
                elif p == "xiaohongshu":
                    home = f"https://www.xiaohongshu.com/user/profile/{sec}"
                else:
                    home = f"https://www.douyin.com/user/{sec}"
            self._on_open_home(home)

        fp = FeaturePanel(
            work_buttons=[
                ("获取链接", _copy_work_link),
                ("查看评论", _show_comments),
                ("下载封面", _download_cover),
            ],
            author_buttons=[
                ("获取作品", self._on_fetch_works),
                ("关注列表", self._on_follow_list),
                ("收藏列表", self._on_collect_list),
                ("下载头像", _dl_avatar),
                ("获取主页", _open_home),
            ],
        )
        fp.execute_clicked.connect(self._on_execute)
        fp.stop_recording_clicked.connect(self._on_stop_recording)
        self._current_worker = None
        return fp

    # ---------------- 侧栏 (每行加框) ----------------
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(12, 12, 12, 12)
        sb.setSpacing(10)

        brand_title = QLabel("MediaDownloader")
        brand_title.setObjectName("BrandTitle")
        sb.addWidget(brand_title)
        brand_caption = QLabel("多平台媒体下载")
        brand_caption.setObjectName("BrandSubtitle")
        sb.addWidget(brand_caption)

        plat_lay = self._side_group(sb, "平台")
        self._platform_btns = []
        for pid in PlatformBus.list_platforms():
            label = _pn(pid)
            btn = QPushButton(label)
            btn.setObjectName("SidebarButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=pid: self._select_platform(p))
            plat_lay.addWidget(btn)
            self._platform_btns.append((pid, btn))

        tool_lay = self._side_group(sb, "工具")
        for text, slot in (
            ("设置",     self._open_settings),
            ("打开下载目录", self._open_download_dir),
            ("切换主题", self._toggle_theme),
        ):
            btn = QPushButton(text)
            btn.setObjectName("SidebarButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            tool_lay.addWidget(btn)
        self._theme_btn = tool_lay.itemAt(tool_lay.count() - 1).widget()

        acc_lay = self._side_group(sb, "账号")
        login_btn = QPushButton("登录 / Cookie")
        login_btn.setObjectName("SidebarButton")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.clicked.connect(self._open_login)
        acc_lay.addWidget(login_btn)

        sb.addSpacing(4)
        version_label = QLabel(f"v{__VERSION__}")
        version_label.setObjectName("VersionLabel")
        sb.addWidget(version_label)
        return sidebar

    _GROUP_STYLE = (
        "QFrame#SideGroup { background: #1e293b;"
        " border: 1px solid #334155; border-radius: 8px; }")

    def _side_group(self, lay: QVBoxLayout, title: str) -> QVBoxLayout:
        card = QFrame()
        card.setObjectName("SideGroup")
        card.setStyleSheet(self._GROUP_STYLE)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(6)
        lbl = QLabel(title)
        lbl.setObjectName("GroupTitle")
        inner.addWidget(lbl)
        lay.addWidget(card)
        return inner

    # ---------------- 状态栏 ----------------
    def _setup_status_bar(self):
        sb = self.statusBar()
        sb.setObjectName("StatusBar")
        self._cookie_label = QLabel("Cookie:")
        self._cookie_label.setObjectName("StatusLabel")
        sb.addWidget(self._cookie_label)
        self._cookie_platform = QLabel("未选择平台")
        self._cookie_platform.setObjectName("StatusPlatform")
        sb.addWidget(self._cookie_platform)
        self._cookie_status = QLabel("—")
        self._cookie_status.setObjectName("StatusCookie")
        sb.addWidget(self._cookie_status)
        self._cookie_hint = QLabel("")
        self._cookie_hint.setObjectName("StatusHint")
        sb.addWidget(self._cookie_hint, 1)
        self._version_label = QLabel(APP_VERSION_LABEL)
        self._version_label.setObjectName("StatusVersion")
        sb.addPermanentWidget(self._version_label)
        self._status_ffmpeg = QLabel("")
        self._status_ffmpeg.setObjectName("StatusFFmpeg")
        sb.addPermanentWidget(self._status_ffmpeg)
        ok, _ = FFmpegManager.check_available()
        self._status_ffmpeg.setText(f"FFmpeg {'✓' if ok else '✗'}")

    def _refresh_cookie_status(self):
        pid = self._current_platform
        if not pid:
            self._cookie_platform.setText("未选择平台")
            self._cookie_status.setText("—")
            self._cookie_hint.setText("")
            return
        cookie = self._cm.get(pid)
        name = _pn(pid)
        self._cookie_platform.setText(name)
        if cookie and cookie.strip():
            length = len(cookie)
            hint = self._cookie_key_hint(pid)
            if hint and not all(k in cookie for k in hint.split("|")):
                self._cookie_status.setText("⚠")
                self._cookie_hint.setText(f"Cookie 不完整 (建议含: {hint})")
            else:
                self._cookie_status.setText("✓")
                self._cookie_hint.setText(
                    f"已配置 ({length} 字符)"
                    + (f" · 含 {hint}" if hint else ""))
        else:
            self._cookie_status.setText("✗")
            self._cookie_hint.setText("未配置 (登录后才有)")

    @staticmethod
    def _cookie_key_hint(platform: str) -> str:
        return {
            "douyin": "ttwid|msToken|sessionid",
            "bilibili": "SESSDATA|bili_jct",
            "kuaishou": "did",
            "xiaohongshu": "web_session",
        }.get(platform, "")

    # ---------------- 平台选择 ----------------
    def _select_platform(self, platform: str):
        self._current_platform = platform
        cookie = self._cm.get(platform)
        features = PlatformBus.get_features(platform)
        self._feature_panel.set_features(features)
        for pid, btn in self._platform_btns:
            btn.setProperty("active", pid == platform)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._video_info.show_empty()
        self._feature_panel.set_work_available(False)
        self._log.clear()
        self._author_panel.show_placeholder(
            f"已选择 {_pn(platform)}", "正在加载当前登录用户...")
        self._refresh_cookie_status()
        try:
            ops = PlatformBus.get_ops(platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self._login_page.setup(platform, hint, cookie)
        if cookie:
            self._load_current_user(platform, cookie)

    def _load_current_user(self, platform: str, cookie: str):
        self._log.append("▸ 启动后台任务获取当前用户...", "#38bdf8")
        task = _UserFetchTask(cookie, platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_user_loaded)
        task.signals.failed.connect(self._on_user_load_failed)
        self._pool.start(task)

    def _on_user_loaded(self, result):
        if not result:
            self._log.append("✗ API 未返回用户 (Cookie 可能失效)", "#ef4444")
            self._author_panel.show_placeholder("当前用户未获取", "Cookie 可能失效或未登录")
            return
        self._log.append(f"✓ 当前用户: {result.get('nickname', '?')}", "#22c55e")
        self._current_user_profile = result
        self._author_panel.show_current_user(result)

    def _on_user_load_failed(self, err: str):
        self._log.append(f"✗ 加载当前用户失败: {err}", "#ef4444")
        self._author_panel.show_placeholder("当前用户加载失败", err[:40])

    # ---------------- 作者功能 ----------------
    def _on_fetch_works(self):
        profile = self._author_panel.profile
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 作者 sec_user_id 未获取", "#f59e0b")
            return
        self._log.append(f"▸ 获取作者所有作品: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("works", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_works_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._pool.start(task)

    def _on_follow_list(self):
        cur = self._current_user_profile or {}
        shown = self._author_panel.profile
        profile = cur if not (shown.get("sec_user_id") and "当前登录" in shown.get("nickname", "")) else shown
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 未获取到当前登录用户", "#f59e0b")
            return
        self._log.append(f"📋 关注列表: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("following", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_following_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._pool.start(task)

    def _on_collect_list(self):
        cur = self._current_user_profile or {}
        profile = cur or self._author_panel.profile
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 未获取到当前登录用户", "#f59e0b")
            return
        self._log.append(f"⭐ 收藏列表: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("collection", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_collection_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._pool.start(task)

    def _on_works_loaded(self, items):
        self._open_works_page("作者所有作品", items)

    def _on_collection_loaded(self, items):
        self._open_works_page("收藏列表", items)

    def _on_following_loaded(self, items):
        if not items:
            self._log.append("⚠ 关注列表: 没有数据", "#f59e0b")
            return
        key = f"following.{self._current_user_profile.get('sec_user_id', 'me') if self._current_user_profile else 'me'}"
        page = UsersPage(title="关注列表")
        page.set_users(items, title="关注列表")
        self._tabs.add_page(key, "关注列表", page)

    def _on_author_task_failed(self, err: str):
        self._log.append(f"✗ {err}", "#ef4444")

    # ---------------- 内嵌页 (替代弹窗) ----------------
    def _open_works_page(self, title: str, items: list[dict]):
        if not items:
            self._log.append(f"⚠ {title}: 没有数据", "#f59e0b")
            return
        key = f"works.{self._current_platform}.{title}"
        page = WorkGridPage()
        page.set_works(items, title=title)
        page.download_requested.connect(self._on_download_selected)
        self._tabs.add_page(key, title, page)
        self._log.append(f"✓ {title}: {len(items)} 个作品 (已打开)", "#22c55e")

    def _open_data_page(self, title: str, data: list,
                        weights: list | None = None):
        if not data:
            return
        if isinstance(data[0], dict):
            keys = list(data[0].keys())[:6]
            headers = [str(k) for k in keys]

            def _val(v):
                s = str(v) if v is not None else ""
                return (s[:40] + "…") if len(s) > 40 else (s or "—")

            rows = [[_val(d.get(k, "")) for k in keys] for d in data[:200]]
        else:
            n = max((len(r) if isinstance(r, (list, tuple)) else 1
                     for r in data), default=1)
            headers = ["#"] + [f"值{i}" for i in range(1, n + 1)]
            rows = []
            for i, r in enumerate(data[:200], 1):
                cells = list(r) if isinstance(r, (list, tuple)) else [r]
                rows.append([str(i)] + [str(c)[:40] for c in cells])
        key = f"data.{title}"
        page = DataTablePage(title=title)
        page.set_rows(headers, rows, weights=weights, title=title)
        self._tabs.add_page(key, title, page)

    def _open_comments_page(self, items: list):
        if not items:
            return
        rows = [[c.get("user", "—"), c.get("content", ""),
                 str(c.get("likes", 0))]
                for c in items if c.get("content")]
        page = DataTablePage(title="评论")
        page.set_rows(["用户", "内容", "点赞"], rows,
                      weights=[1, 4, 1], title="评论列表")
        self._tabs.add_page("comments", "评论列表", page)

    def _on_download_selected(self, ids: list):
        if not ids:
            return
        self._log.append(f"✓ 已选择 {len(ids)} 个作品, 开始批量下载", "#22c55e")
        url = (f"https://www.douyin.com/user/"
               + self._author_panel.profile.get("sec_user_id", ""))
        self._on_execute("account", url, selected=ids)

    # ---------------- 设置 / 登录 / 日志 ----------------
    def _open_settings(self):
        self._settings_page._config = ConfigManager.load()
        self._settings_page._suspend = True
        slider = self._settings_page._font_slider
        slider.setValue(self._settings_page._config.font_size)
        self._settings_page._suspend = False
        if not self._tabs.has_page("settings"):
            self._tabs.add_page("settings", "设置", self._settings_page)
        else:
            self._tabs.set_current("settings")

    def _open_login(self):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台", 3000)
            return
        cookie = self._cm.get(self._current_platform)
        try:
            ops = PlatformBus.get_ops(self._current_platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self._login_page.setup(self._current_platform, hint, cookie)
        if not self._tabs.has_page("login"):
            self._tabs.add_page("login", "账号登录", self._login_page)
        else:
            self._tabs.set_current("login")

    def _toggle_theme(self):
        app = QApplication.instance()
        new_theme = _theme.toggle_theme(app)
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText("暗色" if new_theme == "dark" else "亮色")

    def _open_download_dir(self):
        path = str(VOLUME)
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ---------------- 链接 / 预览 ----------------
    def _on_url_changed(self, text: str):
        self._current_url = (text or "").strip()

    def _on_preview(self):
        url = self._url_input.text().strip()
        if not url:
            if not self._current_platform:
                self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
                return
            cookie = self._cm.get(self._current_platform)
            if not cookie:
                self._log.append("⚠ 未配置 Cookie", "#f59e0b")
                return
            self._log.append("正在加载当前登录用户...", "#38bdf8")
            self._load_current_user(self._current_platform, cookie)
            return
        if not self._current_platform:
            self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
            return
        self._current_url = url
        self._log.clear()
        self._log.append(f"[{_pn(self._current_platform)}] 正在解析 {url[:60]}...", "#38bdf8")
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._do_preview(url))
            loop.close()
        except Exception as e:
            self._log.append(f"✗ 预览异常: {e}", "#ef4444")

    # ---------------- 作者 / 作品 操作 ----------------
    def _save_image(self, url: str, subdir: str, prefix: str):
        if not url:
            self._log.append("⚠ 无图片地址", "#f59e0b")
            return
        from PySide6.QtGui import QImage
        from .cover_loader import CoverLoader
        pix = CoverLoader.instance().request(url)
        img = None
        if pix is not None and not pix.isNull():
            img = pix.toImage()
        else:
            try:
                from curl_cffi.requests import get as _get
                r = _get(url, timeout=15, impersonate="chrome146")
                img = QImage()
                img.loadFromData(bytes(r.content))
            except Exception as e:
                self._log.append(f"✗ 下载失败: {e}", "#ef4444")
                return
            if img.isNull():
                self._log.append("✗ 图片数据无效", "#ef4444")
                return
        import time
        d = VOLUME / (self._current_platform or "common") / subdir
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{prefix}_{int(time.time())}.png"
        if img.save(str(path)):
            self._log.append(f"✓ 已保存: {path}", "#22c55e")
        else:
            self._log.append("✗ 保存失败", "#ef4444")

    def _show_link_dialog(self, title: str, url: str):
        if not url:
            self._log.append("⚠ 无链接", "#f59e0b")
            return
        QApplication.clipboard().setText(url)
        self._log.append(f"✓ {title} 已复制: {url}", "#22c55e")
        self.statusBar().showMessage(f"{title} 已复制到剪贴板", 3000)

    def _on_download_avatar(self, url: str):
        self._save_image(url, "avatars", "avatar")

    def _on_open_home(self, url: str):
        self._show_link_dialog("作者主页链接", url)

    def _on_copy_link(self, url: str):
        self._show_link_dialog("作品链接", url)

    def _on_download_cover(self, url: str):
        self._save_image(url, "covers", "cover")

    def _on_show_comments(self, work_id: str):
        if not work_id:
            self._log.append("⚠ 无作品ID, 无法获取评论", "#f59e0b")
            return
        self._log.append(f"💬 获取评论: {work_id}", "#38bdf8")
        task = _AuthorFetchTask("comments", work_id,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_comments_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._pool.start(task)

    def _on_comments_loaded(self, items):
        if not items:
            self._log.append("⚠ 评论: 没有数据", "#f59e0b")
            return
        self._open_comments_page(items)
        self._log.append(f"✓ 评论 {len(items)} 条 (已打开)", "#22c55e")

    async def _do_preview(self, url: str):
        from shared.core.session import create_async_client
        from shared.flow.link import LinkExtractor, LinkType
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        client = create_async_client()
        try:
            links = await LinkExtractor(client).run(url, self._current_platform)
        finally:
            await client.close()
        if not links:
            self._video_info.show_error("未提取到有效链接")
            self._feature_panel.set_work_available(False)
            self._log.append("✗ 未提取到有效链接", "#ef4444")
            return
        link = links[0]
        adapter_cls = get_platform(self._current_platform)
        if not adapter_cls:
            self._log.append("✗ 平台适配器未找到", "#ef4444")
            return
        cookie = self._cm.get(self._current_platform)
        adapter = adapter_cls(config=PlatformConfig(
            name=self._current_platform, display_name="",
            domains=[], cookie=cookie))
        try:
            if link.link_type == LinkType.LIVE:
                self._log.append("⚠ 直播链接暂不支持完整预览", "#f59e0b")
                return
            raw = await adapter.request_detail(link)
            if raw:
                work = adapter.parse_detail(raw)
                if work:
                    work.setdefault("platform", self._current_platform)
                    self._video_info.show_work(work)
                    self._feature_panel.set_work_available(True)
                    self._log.append(
                        f"✓ 解析成功: {work.get('title', '')[:40]}", "#22c55e")
                    sec_uid = work.get("sec_user_id", "")
                    if sec_uid:
                        await self._load_work_author(adapter, sec_uid)
                else:
                    self._video_info.show_error("解析失败")
                    self._feature_panel.set_work_available(False)
                    self._log.append("✗ 解析失败", "#ef4444")
            else:
                self._video_info.show_error("获取详情失败")
                self._feature_panel.set_work_available(False)
                self._log.append("✗ 获取详情失败", "#ef4444")
        finally:
            await adapter.close()

    async def _load_work_author(self, adapter, sec_uid: str):
        try:
            data = await adapter.fetch_user_profile(sec_uid)
            if not data:
                return
            u = data.get("user") or data.get("card") or data.get("data") or {}
            if not isinstance(u, dict):
                u = {}
            if not u and isinstance(data, dict):
                u = data
            profile = norm_user(u, self._current_platform)
            if not profile.get("nickname"):
                return
            self._author_panel.show_work_author(profile)
            self._log.append(f"✓ 作者: {profile['nickname']}", "#22c55e")
        except Exception as e:
            self._log.append(f"⚠ 加载作者信息失败: {e}", "#f59e0b")

    # ---------------- 功能执行 ----------------
    def _on_execute(self, feature_id: str, url: str = "",
                    opts=None, selected=None):
        if not self._current_platform:
            self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
            return
        url = (url or "").strip()
        if not url:
            work = self._video_info.work
            url = (work.get("share_url") or work.get("video_url") or "").strip()
        if not url:
            url = (self._current_url or "").strip()
        if not url:
            url = self._url_input.text().strip()
        if not url and feature_id not in ("hot", "collection"):
            self._log.append("⚠ 请先粘贴链接并解析", "#f59e0b")
            return
        cookie = self._cm.get(self._current_platform)
        save_dir = VOLUME / self._current_platform
        save_dir.mkdir(parents=True, exist_ok=True)
        worker = FeatureWorker(self._current_platform, feature_id, url,
                               cookie, str(save_dir), selected=selected)
        worker.signals.log_line.connect(self._log.append)
        worker.signals.finished.connect(self._on_result)
        worker.signals.error.connect(
            lambda e: self._log.append(f"错误: {e}", "#ef4444"))
        from .widgets.feature_panel import LIVE_FEATURES
        if feature_id in LIVE_FEATURES:
            self._current_worker = worker
            self._feature_panel.set_recording(True)
        self._pool.start(worker)
        self._log.append(
            f"[{_pn(self._current_platform)}] 启动 {feature_id}", "#38bdf8")

    def _on_stop_recording(self):
        if self._current_worker:
            self._current_worker.stop()
            self._log.append("正在停止录制...", "#f59e0b")

    def _on_result(self, result: dict):
        self._current_worker = None
        self._feature_panel.set_recording(False)
        self._log.set_result(result)
        success = result.get("success", False)
        msg = result.get("message", "")
        self.statusBar().showMessage(msg)
        if success and result.get("preview") == "batch":
            items = result.get("data") or []
            self._open_works_page("批量下载预览", items)
        elif success and result.get("data"):
            data = result.get("data") or []
            self._open_data_table(msg, data)

    def _open_data_table(self, title: str, data: list):
        if not data:
            return
        self._open_data_page(title[:24] or "数据", data)

    # ---------------- 字号 / 设置保存 ----------------
    def _apply_font_size(self, value: int):
        app = QApplication.instance()
        if app is None:
            return
        font = QFont(app.font())
        font.setPixelSize(max(10, int(value)))
        app.setFont(font)

    def _on_settings_saved(self):
        cfg = ConfigManager.load()
        self._apply_font_size(cfg.font_size)
        self._log.append("✓ 设置已保存", "#22c55e")

    def closeEvent(self, event):
        try:
            self._login_page.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
