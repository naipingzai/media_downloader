"""主窗口 — 无菜单栏，所有功能整合到侧边栏+主页。"""
import subprocess, sys
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QScrollArea, QVBoxLayout, QWidget,
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
from .widgets.collect_result import OutputResultView
from .widgets.result_view import ResultView


PLATFORM_LABELS = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{PROJECT_NAME}")
        self.setMinimumSize(900, 640)
        self.resize(1280, 860)
        self.menuBar().setVisible(False)
        load_all_platforms()
        self._cm = CookieManager()
        self._current_platform = ""
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(2)
        self._setup_ui()
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

        brand_title = QLabel("MediaDownloader")
        brand_title.setObjectName("BrandTitle")
        brand_caption = QLabel("多平台媒体下载")
        brand_caption.setObjectName("MutedLabel")
        sb.addWidget(brand_title)
        sb.addWidget(brand_caption)
        sb.addSpacing(16)

        section = QLabel("平台选择")
        section.setObjectName("NavSection")
        sb.addWidget(section)
        self._platform_btns = []
        for pid in PlatformBus.list_platforms():
            label = PLATFORM_LABELS.get(pid, pid.title())
            btn = QPushButton(f"  {label}")
            btn.setObjectName("NavButton")
            btn.clicked.connect(lambda checked, p=pid: self._select_platform(p))
            sb.addWidget(btn)
            self._platform_btns.append(btn)

        sb.addStretch()
        settings_btn = QPushButton("  设置")
        settings_btn.setObjectName("NavButton")
        settings_btn.clicked.connect(self._open_settings)
        sb.addWidget(settings_btn)

        open_dir_btn = QPushButton("  打开下载目录")
        open_dir_btn.setObjectName("NavButton")
        open_dir_btn.clicked.connect(self._open_download_dir)
        sb.addWidget(open_dir_btn)

        sb.addSpacing(4)
        version_label = QLabel(f"v{__VERSION__}")
        version_label.setObjectName("Caption")
        sb.addWidget(version_label)
        sb.addSpacing(4)
        self._login_btn = QPushButton("登录 / Cookie")
        self._login_btn.setObjectName("SidebarAction")
        self._login_btn.clicked.connect(self._open_login)
        sb.addWidget(self._login_btn)
        shell.addWidget(sidebar)

        # ===== WORKSPACE =====
        workspace = QWidget()
        workspace.setObjectName("Workspace")
        wl = QVBoxLayout(workspace)
        wl.setContentsMargins(26, 14, 26, 14)
        wl.setSpacing(8)

        header = QHBoxLayout()
        ht = QVBoxLayout()
        ht.setSpacing(2)
        ht.addWidget(QLabel("下载控制台"))
        page_sub = QLabel("支持抖音、快手、小红书、B站的媒体下载与采集工具")
        page_sub.setObjectName("Caption")
        ht.addWidget(page_sub)
        header.addLayout(ht)
        header.addStretch()
        wl.addLayout(header)

        hero = HeroPanel(workspace)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(28, 10, 28, 10)
        self._hero_title = QLabel("MediaDownloader")
        self._hero_title.setObjectName("HeroTitle")
        self._hero_sub = QLabel("选择平台开始")
        self._hero_sub.setObjectName("Caption")
        hl.addWidget(self._hero_title)
        hl.addWidget(self._hero_sub)
        hl.addStretch()
        wl.addWidget(hero)

        content_grid = QGridLayout()
        content_grid.setSpacing(16)
        content_grid.setColumnStretch(0, 1)
        content_grid.setColumnStretch(1, 1)

        self._video_info = VideoInfoWidget(workspace)
        self._feature_panel = FeaturePanel(workspace)
        self._feature_panel.execute_clicked.connect(self._on_execute)
        self._feature_panel.preview_clicked.connect(self._on_preview)

        self._output_result = OutputResultView(workspace)
        self._result_view = ResultView(workspace)

        # 固定最小高度，防止布局跳动
        self._video_info.setMinimumHeight(180)
        self._output_result.setMinimumHeight(180)
        self._feature_panel.setMinimumHeight(240)
        self._result_view.setMinimumHeight(240)

        # 第0行: 作品资料卡 | 采集结果
        content_grid.addWidget(self._video_info, 0, 0)
        content_grid.addWidget(self._output_result, 0, 1)
        # 第1行: 功能与参数 | 执行日志
        content_grid.addWidget(self._feature_panel, 1, 0)
        content_grid.addWidget(self._result_view, 1, 1)

        content_grid.setRowStretch(0, 1)
        content_grid.setRowStretch(1, 1)

        wl.addLayout(content_grid, 1)

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

    def _setup_status_bar(self):
        self.statusBar().setObjectName("StatusBar")
        self.statusBar().showMessage(f"{PROJECT_NAME} v{__VERSION__}")
        # 右侧永久信息
        self._status_ffmpeg = QLabel("")
        self._status_dir = QLabel("")
        self._status_dir.setObjectName("Caption")
        self.statusBar().addPermanentWidget(self._status_dir)
        self.statusBar().addPermanentWidget(self._status_ffmpeg)
        # 初始化显示
        from shared.core.ffmpeg import FFmpegManager
        ok, ver = FFmpegManager.check_available()
        self._status_ffmpeg.setText(f"FFmpeg {'✓' if ok else '✗'}")
        self._status_ffmpeg.setStyleSheet(f"color: {'#22c55e' if ok else '#64748b'}; font-size: 11px;")
        self._status_dir.setText(f"📁 {VOLUME}")

    def _select_platform(self, platform):
        self._current_platform = platform
        features = PlatformBus.get_features(platform)
        self._feature_panel.set_features(features)
        label = PLATFORM_LABELS.get(platform, platform.title())
        self._hero_title.setText(label)
        self._hero_sub.setText(f"{len(features)} 个功能可用")
        self._video_info.show_empty()
        self._result_view.clear()
        self._output_result.show_empty()

    def _open_login(self):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        ops = PlatformBus.get_ops(self._current_platform)
        hint = ops.cookie_hint if ops else ""
        current = self._cm.get(self._current_platform)
        dlg = LoginDialog(self._current_platform, hint, current, self)
        dlg.exec()
        # 对话框保存了新 cookie，重新加载
        self._cm = CookieManager()
        cookie = self._cm.get(self._current_platform)

    def _open_settings(self):
        SettingsDialog(self).exec()

    def _open_download_dir(self):
        path = str(VOLUME)
        if sys.platform == "darwin": subprocess.Popen(["open", path])
        elif sys.platform == "win32": subprocess.Popen(["explorer", path])
        else: subprocess.Popen(["xdg-open", path])

    def _on_preview(self, url):
        if not url.strip():
            self.statusBar().showMessage("请输入链接")
            return
        self._result_view.clear()
        self._output_result.show_empty()
        label = PLATFORM_LABELS.get(self._current_platform, self._current_platform)
        self._result_view.append(f"[{label}] 正在解析...")
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

    def _on_execute(self, feature_id, url, opts=None):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        self._result_view.clear()
        self._output_result.show_empty()
        label = PLATFORM_LABELS.get(self._current_platform, self._current_platform)
        self._result_view.append(f"[{label}] 执行 {feature_id}...")
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
            # 下载结果 → 输出结果面板
            files = result.get("files", [])
            if files:
                self._output_result.set_download_results(files, result.get("message", "下载结果"))
            # 采集数据 → 输出结果面板
            data = result.get("data")
            if data and isinstance(data, list) and len(data) > 0:
                d = data[0]
                if "word" in d:
                    self._output_result.show_hot_list(data)
                elif "user" in d and "text" in d:
                    self._output_result.show_comments(data)
                elif "title" in d and "author" in d:
                    self._output_result.show_search(data)
            elif data and isinstance(data, dict):
                self._output_result.show_user(data)
        else:
            self.statusBar().showMessage(f"失败: {result.get('message', '')}")
