"""主窗口 — 融合 bilibili-downloader 设计。"""
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from shared.core import PROJECT_NAME, VOLUME, __VERSION__
from shared.core.config import ConfigManager
from shared.core.cookies import CookieManager
from shared.core.ops import PlatformBus
from platforms import load_all_platforms, get_platform
from .dialogs.login_dialog import LoginDialog
from .dialogs.settings_dialog import SettingsDialog
from .threads.worker import FeatureWorker
from .widgets.hero_panel import HeroPanel
from .widgets.feature_panel import FeaturePanel
from .widgets.video_info import VideoInfoWidget
from .widgets.collect_result import CollectResultView
from .widgets.result_view import ResultView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{PROJECT_NAME}")
        self.setMinimumSize(900, 640)
        self.resize(1280, 860)
        load_all_platforms()
        self._cm = CookieManager()
        self._current_platform = ""
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(2)
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # ===== SIDEBAR =====
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(18, 22, 18, 18)
        sb.setSpacing(10)

        # Brand
        brand_title = QLabel("MediaDownloader")
        brand_title.setObjectName("BrandTitle")
        brand_caption = QLabel("多平台媒体下载")
        brand_caption.setObjectName("MutedLabel")
        sb.addWidget(brand_title)
        sb.addWidget(brand_caption)
        sb.addSpacing(16)

        # Platform navigation
        section = QLabel("PLATFORMS")
        section.setObjectName("NavSection")
        sb.addWidget(section)
        self._platform_btns = []
        for pid in PlatformBus.list_platforms():
            btn = QPushButton(f"  {pid.title()}")
            btn.setObjectName("NavButton")
            
            btn.clicked.connect(lambda checked, p=pid: self._select_platform(p))
        print("[DEBUG] Button connected:", btn.text().strip())
            sb.addWidget(btn)
            self._platform_btns.append(btn)
        sb.addSpacing(16)

        # Sidebar info card
        info_card = QFrame()
        info_card.setObjectName("InfoCard")
        ic = QVBoxLayout(info_card)
        ic.setContentsMargins(14, 14, 14, 14)
        ic.setSpacing(4)
        info_title = QLabel("功能概览")
        info_title.setObjectName("InfoTitle")
        info_text = QLabel("支持 4 个平台 · 18 个功能\n下载 · 采集 · 批量 · 存储")
        info_text.setObjectName("SidebarCaption")
        info_text.setWordWrap(True)
        ic.addWidget(info_title)
        ic.addWidget(info_text)
        sb.addWidget(info_card)

        sb.addStretch()

        # Login button
        self._login_btn = QPushButton("登录 / Cookie")
        self._login_btn.setObjectName("SidebarAction")
        self._login_btn.clicked.connect(self._open_login)
        print("[DEBUG] Button connected:", btn.text().strip())
        sb.addWidget(self._login_btn)

        shell.addWidget(sidebar)

        # ===== WORKSPACE =====
        workspace = QWidget()
        workspace.setObjectName("Workspace")
        wl = QVBoxLayout(workspace)
        wl.setContentsMargins(26, 22, 26, 16)
        wl.setSpacing(12)

        # Header
        header = QHBoxLayout()
        ht = QVBoxLayout()
        ht.setSpacing(2)
        ht.addWidget(QLabel("下载控制台"))
        page_sub = QLabel("融合 bilibili-downloader 设计，支持多平台媒体下载")
        page_sub.setObjectName("Caption")
        ht.addWidget(page_sub)
        header.addLayout(ht)
        header.addStretch()
        self._header_login = QPushButton("未登录")
        self._header_login.setObjectName("GhostButton")
        self._header_login.clicked.connect(self._open_login)
        header.addWidget(self._header_login)
        wl.addLayout(header)

        # HeroPanel
        hero = HeroPanel(workspace)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(28, 24, 28, 26)
        self._hero_title = QLabel("MediaDownloader")
        self._hero_title.setObjectName("HeroTitle")
        self._hero_sub = QLabel("选择平台开始使用")
        self._hero_sub.setStyleSheet("color: #94a3b8; font-size: 13px;")
        hl.addWidget(self._hero_title)
        hl.addWidget(self._hero_sub)
        hl.addStretch()
        wl.addWidget(hero)

        # Content: horizontal layout
        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        # Left: VideoInfo + FeaturePanel
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        self._video_info = VideoInfoWidget(workspace)
        left_col.addWidget(self._video_info, 2)

        self._feature_panel = FeaturePanel(workspace)
        self._feature_panel.execute_clicked.connect(self._on_execute)
        self._feature_panel.preview_clicked.connect(self._on_preview)
        left_col.addWidget(self._feature_panel, 1)
        content_row.addLayout(left_col, 5)

        # Right: Result + CollectResult
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self._result_view = ResultView(workspace)
        right_col.addWidget(self._result_view, 2)

        self._collect_result = CollectResultView(workspace)
        right_col.addWidget(self._collect_result, 1)
        content_row.addLayout(right_col, 5)

        wl.addLayout(content_row, 1)

        # Download queue header
        qh = QHBoxLayout()
        qh.addWidget(QLabel("任务队列"))
        qh.addStretch()
        pause_btn = QPushButton("全部暂停")
        pause_btn.setObjectName("SubtleButton")
        qh.addWidget(pause_btn)
        resume_btn = QPushButton("全部继续")
        resume_btn.setObjectName("SubtleButton")
        qh.addWidget(resume_btn)
        clear_btn = QPushButton("清除完成")
        clear_btn.setObjectName("SubtleButton")
        qh.addWidget(clear_btn)
        wl.addLayout(qh)

        shell.addWidget(workspace, 1)

    def _setup_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("文件")
        file_menu.addAction("登录/Cookie", self._open_login)
        file_menu.addAction("设置", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        view_menu = mb.addMenu("视图")
        view_menu.addAction("打开下载目录", self._open_download_dir)

        help_menu = mb.addMenu("帮助")
        help_menu.addAction("关于", lambda: self.statusBar().showMessage(f"{PROJECT_NAME} v{__VERSION__}"))

    def _setup_status_bar(self):
        self._status_platform = QLabel("")
        self._status_feature = QLabel("")
        self._status_cookie = QLabel("")
        self.statusBar().addPermanentWidget(self._status_platform)
        self.statusBar().addPermanentWidget(self._status_feature)
        self.statusBar().addPermanentWidget(self._status_cookie)
        self.statusBar().showMessage(f"{PROJECT_NAME} v{__VERSION__}")

    def _select_platform(self, platform):
        print("[DEBUG] _select_platform called with:", platform)
        self._current_platform = platform
        features = PlatformBus.get_features(platform)
        self._feature_panel.set_features(features)
        self._hero_title.setText(platform.title())
        self._hero_sub.setText(f"{len(features)} 个功能可用")
        ops = PlatformBus.get_ops(platform)
        cookie = self._cm.get(platform)
        hint = ops.cookie_hint if ops else ""
        cookie_text = f"Cookie: {'已设置 ' + str(len(cookie)) + '字符' if cookie else '未设置'}" if hint else "Cookie: 不需要"
        self._status_platform.setText(f"平台: {platform}")
        self._status_cookie.setText(cookie_text)
        self._header_login.setText(f"{platform.title()} {'已登录' if cookie else '未登录'}")
        self._video_info.show_empty()
        self._result_view.clear()
        self._collect_result.show_empty()

    def _open_login(self):
        print("[DEBUG] _open_login called")
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        ops = PlatformBus.get_ops(self._current_platform)
        hint = ops.cookie_hint if ops else ""
        current = self._cm.get(self._current_platform)
        dlg = LoginDialog(self._current_platform, hint, current, self)
        dlg.exec()
        cookie = self._cm.get(self._current_platform)
        cookie_text = f"Cookie: {'已设置 ' + str(len(cookie)) + '字符' if cookie else '未设置'}"
        self._status_cookie.setText(cookie_text)
        self._header_login.setText(f"{self._current_platform.title()} {'已登录' if cookie else '未登录'}")

    def _open_settings(self):
        print("[DEBUG] _open_settings called")
        SettingsDialog(self).exec()

    def _open_download_dir(self):
        import subprocess, sys
        path = str(VOLUME)
        if sys.platform == "darwin": subprocess.Popen(["open", path])
        elif sys.platform == "win32": subprocess.Popen(["explorer", path])
        else: subprocess.Popen(["xdg-open", path])

    def _on_preview(self, url):
        print("[DEBUG] _on_preview called:", url)
        if not url.strip():
            self.statusBar().showMessage("请输入链接")
            return
        self._result_view.clear()
        self._result_view.append("正在解析...", "#94a3b8")
        import asyncio
        from shared.core.session import create_async_client
        from shared.flow.link import LinkExtractor
        async def _do():
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, self._current_platform)
                if links:
                    adapter_cls = get_platform(self._current_platform)
                    if adapter_cls:
                        from shared.core.adapter import PlatformConfig
                        adapter = adapter_cls(config=PlatformConfig(
                            name=self._current_platform, display_name="",
                            domains=[], cookie=self._cm.get(self._current_platform)))
                        raw = await adapter.request_detail(links[0])
                        if raw:
                            work = adapter.parse_detail(raw)
                            if work:
                                self._video_info.show_work(work)
                                self._result_view.append("解析成功", "#22c55e")
                            else:
                                self._video_info.show_error("解析失败")
                                self._result_view.append("解析失败", "#ef4444")
                        else:
                            self._video_info.show_error("获取详情失败")
                        await adapter.close()
                    else:
                        self._result_view.append("平台适配器未找到", "#ef4444")
                else:
                    self._video_info.show_error("未提取到有效链接")
                    self._result_view.append("未提取到有效链接", "#ef4444")
            finally:
                await client.close()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_do())
        loop.close()

    def _on_execute(self, feature_id, url, output_fmt, storage_mode):
        print("[DEBUG] _on_execute called:", feature_id)
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        self._result_view.clear()
        self._result_view.append(f"执行: {feature_id}")
        self._status_feature.setText(f"功能: {feature_id}")
        cookie = self._cm.get(self._current_platform)
        save_dir = VOLUME / self._current_platform
        save_dir.mkdir(parents=True, exist_ok=True)
        worker = FeatureWorker(self._current_platform, feature_id, url, cookie, str(save_dir))
        worker.signals.log_line.connect(lambda t: self._result_view.append(t))
        worker.signals.work_info.connect(lambda w: self._video_info.show_work(w))
        worker.signals.finished.connect(self._on_result)
        worker.signals.error.connect(lambda e: self._result_view.append(f"错误: {e}", "#ef4444"))
        self._pool.start(worker)

    def _on_result(self, result):
        self._result_view.set_result(result)
        if result.get("success"):
            self.statusBar().showMessage(result.get("message", "完成"))
            data = result.get("data")
            if data and isinstance(data, list) and len(data) > 0:
                d = data[0]
                if "word" in d:
                    self._collect_result.show_hot_list(data)
                elif "user" in d and "text" in d:
                    self._collect_result.show_comments(data)
                elif "title" in d and "author" in d:
                    self._collect_result.show_search(data)
            elif data and isinstance(data, dict):
                self._collect_result.show_user(data)
        else:
            self.statusBar().showMessage(f"失败: {result.get('message', '')}")
