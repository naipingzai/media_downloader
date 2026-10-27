"""内嵌设置页 —— 替代 SettingsDialog。

卡片分组: 存储 / 输出格式 / 下载选项 / 下载队列 / FFmpeg / 外观 (字号)
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)
from shared.core import ConfigManager, FFmpegManager
from shared.core.formats import OUTPUT_PROFILES, VIDEO_CODECS, AUDIO_CODECS


IMAGE_FORMATS = [
    ("PNG", "png"),
    ("JPEG", "jpg"),
    ("WebP", "webp"),
    ("GIF", "gif"),
    ("BMP", "bmp"),
    ("原始 (不处理)", "raw"),
]


class SettingsPage(QWidget):
    """内嵌设置页 (单例)。"""
    settings_saved = Signal()   # 保存成功 → main_window 刷新字体
    font_changed = Signal(int)  # 实时调字号 → main_window 立即应用

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager.load()
        self._suspend = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # 顶部标题 + 保存按钮 (页头即保存, 不用滚到底部)
        head = QHBoxLayout()
        title = QLabel("应用设置")
        title.setObjectName("PageTitle")
        head.addWidget(title)
        head.addStretch()
        self._status = QLabel("")
        self._status.setObjectName("PageStatus")
        head.addWidget(self._status)
        save_head = QPushButton("保存")
        save_head.setObjectName("PagePrimaryButton")
        save_head.setCursor(Qt.PointingHandCursor)
        save_head.clicked.connect(self._save)
        head.addWidget(save_head)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self._cards_lay = QVBoxLayout(container)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(10)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self._build_cards()

        # 底部保存按钮
        bot = QHBoxLayout()
        bot.addStretch()
        self._save_btn = QPushButton("保存")
        self._save_btn.setObjectName("PagePrimaryButton")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)
        root.addLayout(bot)

    def _build_cards(self):
        # 存储
        self._cards_lay.addWidget(self._build_storage_card())
        # 输出格式
        self._cards_lay.addWidget(self._build_output_card())
        # 下载选项
        self._cards_lay.addWidget(self._build_download_card())
        # 下载队列 (限速/暂停/恢复)
        self._cards_lay.addWidget(self._build_queue_card())
        # FFmpeg
        self._cards_lay.addWidget(self._build_ffmpeg_card())
        # 外观
        self._cards_lay.addWidget(self._build_appearance_card())
        self._cards_lay.addStretch()

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("PageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        lbl = QLabel(title)
        lbl.setObjectName("CardTitle")
        lay.addWidget(lbl)
        return card, lay

    def _build_storage_card(self) -> QWidget:
        card, lay = self._make_card("存储")
        self._mode = QComboBox()
        for name, val in [("直接存储", "flat"), ("按作者分目录", "by_author"),
                          ("按日期分目录", "by_date"), ("按类型分目录", "by_type")]:
            self._mode.addItem(name, val)
        idx = self._mode.findData(self._config.storage_mode)
        if idx >= 0:
            self._mode.setCurrentIndex(idx)
        self._fmt = QComboBox()
        for name, val in [("JSON", "json"), ("CSV", "csv")]:
            self._fmt.addItem(name, val)
        idx = self._fmt.findData(self._config.storage_format)
        if idx >= 0:
            self._fmt.setCurrentIndex(idx)
        self._dedup = QCheckBox("启用去重")
        self._dedup.setChecked(self._config.dedup)
        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("存储模式:", self._mode)
        form.addRow("数据格式:", self._fmt)
        form.addRow("去重:", self._dedup)
        lay.addLayout(form)
        return card

    def _build_output_card(self) -> QWidget:
        card, lay = self._make_card("输出格式")
        self._profile = QComboBox()
        for key, prof in OUTPUT_PROFILES.items():
            self._profile.addItem(prof.name, key)
        idx = self._profile.findData(self._config.default_profile)
        if idx >= 0:
            self._profile.setCurrentIndex(idx)
        self._vcodec = QComboBox()
        for key, vc in VIDEO_CODECS.items():
            self._vcodec.addItem(vc.name, key)
        idx = self._vcodec.findData(self._config.default_video_codec)
        if idx >= 0:
            self._vcodec.setCurrentIndex(idx)
        self._acodec = QComboBox()
        for key, ac in AUDIO_CODECS.items():
            self._acodec.addItem(ac.name, key)
        idx = self._acodec.findData(self._config.default_audio_codec)
        if idx >= 0:
            self._acodec.setCurrentIndex(idx)
        self._img_fmt = QComboBox()
        for name, val in IMAGE_FORMATS:
            self._img_fmt.addItem(name, val)
        idx = self._img_fmt.findData(self._config.default_image_format)
        if idx >= 0:
            self._img_fmt.setCurrentIndex(idx)
        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("视频预设:", self._profile)
        form.addRow("视频编码:", self._vcodec)
        form.addRow("音频编码:", self._acodec)
        form.addRow("图片格式:", self._img_fmt)
        lay.addLayout(form)
        return card

    def _build_download_card(self) -> QWidget:
        card, lay = self._make_card("下载选项")
        self._dl_danmaku = QCheckBox("弹幕")
        self._dl_danmaku.setChecked(self._config.download_danmaku)
        self._dl_subtitle = QCheckBox("字幕")
        self._dl_subtitle.setChecked(self._config.download_subtitle)
        self._dl_cover = QCheckBox("封面")
        self._dl_cover.setChecked(self._config.download_cover)
        self._dl_metadata = QCheckBox("元数据")
        self._dl_metadata.setChecked(self._config.download_metadata)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._dl_danmaku)
        row.addWidget(self._dl_subtitle)
        row.addWidget(self._dl_cover)
        row.addWidget(self._dl_metadata)
        row.addStretch()
        lay.addLayout(row)
        return card

    def _build_queue_card(self) -> QWidget:
        """下载队列控制: 全局限速 + 暂停/恢复 (实时生效)。"""
        card, lay = self._make_card("下载队列")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("限速 (KB/s, 0=不限):"))
        self._speed_input = QLineEdit(str(self._config.speed_limit))
        self._speed_input.setFixedWidth(90)
        self._speed_input.setPlaceholderText("0")
        row.addWidget(self._speed_input)
        self._pause_btn = QPushButton("暂停全部")
        self._pause_btn.setObjectName("PageGhostButton")
        self._pause_btn.setCursor(Qt.PointingHandCursor)
        self._pause_btn.clicked.connect(self._toggle_pause)
        row.addWidget(self._pause_btn)
        row.addStretch()
        lay.addLayout(row)
        hint = QLabel("限速保存后全局生效; 暂停/恢复立即作用于进行中的下载")
        hint.setObjectName("CardHint")
        lay.addWidget(hint)
        self._sync_pause_btn()
        return card

    def _sync_pause_btn(self):
        try:
            from shared.flow.queue import get_queue
            paused = get_queue().paused
        except Exception:
            paused = False
        self._pause_btn.setText("恢复下载" if paused else "暂停全部")

    def _toggle_pause(self):
        from shared.flow.queue import get_queue
        q = get_queue()
        if q.paused:
            q.resume_all()
        else:
            q.pause_all()
        self._sync_pause_btn()

    def _build_ffmpeg_card(self) -> QWidget:
        card, lay = self._make_card("FFmpeg")
        ffmpeg_display = self._config.ffmpeg_path
        if not ffmpeg_display:
            exe = FFmpegManager.find_executable()
            ffmpeg_display = str(exe) if exe else ""
        self._ffmpeg = QLineEdit(ffmpeg_display)
        self._ffmpeg.setPlaceholderText("自动检测系统 FFmpeg 或手动输入路径")
        browse = QPushButton("浏览…")
        browse.setObjectName("PageGhostButton")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._ffmpeg, 1)
        row.addWidget(browse)
        lay.addLayout(row)
        # 状态
        try:
            ok, msg = FFmpegManager.check_available(
                self._config.ffmpeg_path or None)
        except Exception:
            ok, msg = False, "FFmpeg 检测超时"
        self._ffmpeg_status = QLabel(
            f"{'✓ ' if ok else '✗ '}{msg}")
        self._ffmpeg_status.setStyleSheet(
            f"color: {'#22c55e' if ok else '#ef4444'};"
            " font-size: 12px; background: transparent; border: none;")
        lay.addWidget(self._ffmpeg_status)
        return card

    def _build_appearance_card(self) -> QWidget:
        card, lay = self._make_card("外观")
        # 字号滑块
        srow = QHBoxLayout()
        srow.setSpacing(10)
        srow.addWidget(QLabel("12"))
        self._font_slider = QSlider(Qt.Horizontal)
        self._font_slider.setRange(12, 20)
        self._font_slider.setValue(self._config.font_size)
        self._font_slider.setTickPosition(QSlider.TicksBelow)
        self._font_slider.setTickInterval(2)
        self._font_slider.valueChanged.connect(self._on_font_changed)
        srow.addWidget(self._font_slider, 1)
        srow.addWidget(QLabel("20"))
        self._font_value_label = QLabel(f"{self._config.font_size} px")
        self._font_value_label.setObjectName("FontSizeLabel")
        srow.addWidget(self._font_value_label)
        lay.addLayout(srow)
        hint = QLabel("调整后立即生效, 程序启动时自动应用")
        hint.setObjectName("CardHint")
        lay.addWidget(hint)
        return card

    def _on_font_changed(self, value: int):
        self._font_value_label.setText(f"{value} px")
        if self._suspend:
            return
        # 实时生效 (只调字号, 不持久化, 保存时一起写)
        self.font_changed.emit(int(value))

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 FFmpeg")
        if path:
            self._ffmpeg.setText(path)

    def _save(self):
        try:
            self._config.storage_mode = self._mode.currentData() or "flat"
            self._config.storage_format = self._fmt.currentData() or "json"
            self._config.dedup = self._dl_danmaku is not None and self._dedup.isChecked()
            self._config.default_profile = self._profile.currentData() or "mp4_copy"
            self._config.default_video_codec = self._vcodec.currentData() or "copy"
            self._config.default_audio_codec = self._acodec.currentData() or "copy"
            self._config.default_image_format = self._img_fmt.currentData() or "png"
            self._config.download_danmaku = self._dl_danmaku.isChecked()
            self._config.download_subtitle = self._dl_subtitle.isChecked()
            self._config.download_cover = self._dl_cover.isChecked()
            self._config.download_metadata = self._dl_metadata.isChecked()
            self._config.ffmpeg_path = self._ffmpeg.text().strip()
            self._config.font_size = int(self._font_slider.value())
            # 限速: 持久化 + 立即应用到队列
            try:
                limit = max(0, int(self._speed_input.text().strip() or "0"))
            except ValueError:
                limit = 0
            self._config.speed_limit = limit
            try:
                from shared.flow.queue import get_queue
                get_queue().set_speed_limit(limit)
            except Exception:
                pass
            ConfigManager.save(self._config)
            self._status.setText("✓ 已保存")
            self.settings_saved.emit()
        except Exception as e:
            self._status.setText(f"✗ 保存失败: {e}")
