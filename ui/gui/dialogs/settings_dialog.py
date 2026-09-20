"""设置对话框 — 全局默认配置。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget, QGroupBox, QFrame,
)
from shared.core.config import ConfigManager, AppConfig
from shared.core.ffmpeg import FFmpegManager
from shared.core.formats import (
    ContainerFormat, VIDEO_CODECS, AUDIO_CODECS, OUTPUT_PROFILES,
)

IMAGE_FORMATS = [
    ("PNG", "png"),
    ("JPEG", "jpg"),
    ("WebP", "webp"),
    ("GIF", "gif"),
    ("BMP", "bmp"),
    ("原始 (不处理)", "raw"),
]


def _sep():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #334155;")
    return line


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用设置")
        self.setMinimumWidth(620)
        self.setMinimumHeight(580)
        self._config = ConfigManager.load()
        self._setup_ui()

    def _setup_ui(self):
        from PySide6.QtWidgets import QSizePolicy
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        title = QLabel("应用设置")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        # ── 共享表单布局 ──
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ── 存储 ──
        lbl_store = QLabel("存储")
        lbl_store.setStyleSheet("color: #22d3ee; font-weight: bold; font-size: 13px; margin-top: 4px;")
        form.addRow(lbl_store)

        self._mode = QComboBox()
        self._mode.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name, val in [("直接存储", "flat"), ("按作者分目录", "by_author"),
                         ("按日期分目录", "by_date"), ("按类型分目录", "by_type")]:
            self._mode.addItem(name, val)
        idx = self._mode.findData(self._config.storage_mode)
        if idx >= 0: self._mode.setCurrentIndex(idx)
        form.addRow("存储模式:", self._mode)

        self._fmt = QComboBox()
        self._fmt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name, val in [("JSON", "json"), ("CSV", "csv")]:
            self._fmt.addItem(name, val)
        idx = self._fmt.findData(self._config.storage_format)
        if idx >= 0: self._fmt.setCurrentIndex(idx)
        form.addRow("数据格式:", self._fmt)

        self._dedup = QCheckBox("启用去重")
        self._dedup.setChecked(self._config.dedup)
        form.addRow("去重:", self._dedup)

        form.addRow(_sep())

        # ── 输出格式 ──
        lbl_fmt = QLabel("输出格式")
        lbl_fmt.setStyleSheet("color: #22d3ee; font-weight: bold; font-size: 13px; margin-top: 4px;")
        form.addRow(lbl_fmt)

        self._profile = QComboBox()
        self._profile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, prof in OUTPUT_PROFILES.items():
            self._profile.addItem(prof.name, key)
        idx = self._profile.findData(self._config.default_profile)
        if idx >= 0: self._profile.setCurrentIndex(idx)
        form.addRow("视频预设:", self._profile)

        self._vcodec = QComboBox()
        self._vcodec.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, vc in VIDEO_CODECS.items():
            self._vcodec.addItem(vc.name, key)
        idx = self._vcodec.findData(self._config.default_video_codec)
        if idx >= 0: self._vcodec.setCurrentIndex(idx)
        form.addRow("视频编码:", self._vcodec)

        self._acodec = QComboBox()
        self._acodec.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, ac in AUDIO_CODECS.items():
            self._acodec.addItem(ac.name, key)
        idx = self._acodec.findData(self._config.default_audio_codec)
        if idx >= 0: self._acodec.setCurrentIndex(idx)
        form.addRow("音频编码:", self._acodec)

        self._img_fmt = QComboBox()
        self._img_fmt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name, val in IMAGE_FORMATS:
            self._img_fmt.addItem(name, val)
        idx = self._img_fmt.findData(self._config.default_image_format)
        if idx >= 0: self._img_fmt.setCurrentIndex(idx)
        form.addRow("图片格式:", self._img_fmt)

        form.addRow(_sep())

        # ── 下载选项 ──
        lbl_dl = QLabel("下载选项")
        lbl_dl.setStyleSheet("color: #22d3ee; font-weight: bold; font-size: 13px; margin-top: 4px;")
        form.addRow(lbl_dl)

        self._dl_danmaku = QCheckBox("弹幕")
        self._dl_danmaku.setChecked(self._config.download_danmaku)
        self._dl_subtitle = QCheckBox("字幕")
        self._dl_subtitle.setChecked(self._config.download_subtitle)
        self._dl_cover = QCheckBox("封面")
        self._dl_cover.setChecked(self._config.download_cover)
        self._dl_metadata = QCheckBox("元数据")
        self._dl_metadata.setChecked(self._config.download_metadata)
        r_dl = QHBoxLayout()
        r_dl.addWidget(self._dl_danmaku)
        r_dl.addWidget(self._dl_subtitle)
        r_dl.addWidget(self._dl_cover)
        r_dl.addWidget(self._dl_metadata)
        r_dl.addStretch()
        form.addRow("默认选择:", r_dl)

        form.addRow(_sep())

        # ── FFmpeg ──
        lbl_ff = QLabel("FFmpeg")
        lbl_ff.setStyleSheet("color: #22d3ee; font-weight: bold; font-size: 13px; margin-top: 4px;")
        form.addRow(lbl_ff)

        ff_row = QHBoxLayout()
        ffmpeg_display = self._config.ffmpeg_path
        if not ffmpeg_display:
            exe = FFmpegManager.find_executable()
            ffmpeg_display = str(exe) if exe else ""
        self._ffmpeg = QLineEdit(ffmpeg_display)
        self._ffmpeg.setPlaceholderText("自动检测系统 FFmpeg 或手动输入路径")
        ff_row.addWidget(self._ffmpeg, 1)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse)
        ff_row.addWidget(browse)
        form.addRow("路径:", ff_row)

        try:
            ok, msg = FFmpegManager.check_available(self._config.ffmpeg_path or None)
        except Exception:
            ok, msg = False, "FFmpeg 检测超时"
        status = QLabel(f"{'✓ ' + msg if ok else '✗ ' + msg}")
        status.setStyleSheet(f"color: {'#22c55e' if ok else '#ef4444'}; font-size: 11px;")
        form.addRow("", status)

        root.addLayout(form)
        root.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _browse(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择 FFmpeg")
        if path: self._ffmpeg.setText(path)

    def _save(self):
        self._config.storage_mode = self._mode.currentData()
        self._config.storage_format = self._fmt.currentData()
        self._config.dedup = self._dedup.isChecked()
        self._config.default_profile = self._profile.currentData()
        self._config.default_video_codec = self._vcodec.currentData()
        self._config.default_audio_codec = self._acodec.currentData()
        self._config.default_image_format = self._img_fmt.currentData()
        self._config.download_danmaku = self._dl_danmaku.isChecked()
        self._config.download_subtitle = self._dl_subtitle.isChecked()
        self._config.download_cover = self._dl_cover.isChecked()
        self._config.download_metadata = self._dl_metadata.isChecked()
        self._config.ffmpeg_path = self._ffmpeg.text().strip()
        ConfigManager.save(self._config)
        self.accept()
