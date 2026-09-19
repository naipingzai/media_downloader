"""设置对话框 — 完整格式配置。"""
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)
from shared.core.config import ConfigManager
from shared.core.ffmpeg import FFmpegManager
from shared.core.formats import (
    ContainerFormat, VIDEO_CODECS, AUDIO_CODECS, OUTPUT_PROFILES,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(580)
        self._config = ConfigManager.load()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("应用设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #facc15;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        # 存储设置
        self._mode = QComboBox()
        for name, val in [("直接存储", "flat"), ("按作者分目录", "by_author"),
                         ("按日期分目录", "by_date"), ("按类型分目录", "by_type")]:
            self._mode.addItem(name, val)
        idx = self._mode.findData(self._config.storage_mode)
        if idx >= 0: self._mode.setCurrentIndex(idx)
        form.addRow("存储模式:", self._mode)

        self._fmt = QComboBox()
        for name, val in [("JSON", "json"), ("CSV", "csv")]:
            self._fmt.addItem(name, val)
        idx = self._fmt.findData(self._config.storage_format)
        if idx >= 0: self._fmt.setCurrentIndex(idx)
        form.addRow("数据格式:", self._fmt)

        self._dedup = QCheckBox("启用去重")
        self._dedup.setChecked(self._config.dedup)
        form.addRow("", self._dedup)

        # 默认输出格式
        self._profile = QComboBox()
        for key, prof in OUTPUT_PROFILES.items():
            self._profile.addItem(prof.name, key)
        form.addRow("默认输出:", self._profile)

        # 默认视频编码
        self._vcodec = QComboBox()
        for key, vc in VIDEO_CODECS.items():
            self._vcodec.addItem(vc.name, key)
        self._vcodec.setCurrentText("直接复制 (不转码)")
        form.addRow("视频编码:", self._vcodec)

        # 默认音频编码
        self._acodec = QComboBox()
        for key, ac in AUDIO_CODECS.items():
            self._acodec.addItem(ac.name, key)
        self._acodec.setCurrentText("直接复制")
        form.addRow("音频编码:", self._acodec)

        layout.addLayout(form)

        # FFmpeg 设置
        ff_layout = QHBoxLayout()
        self._ffmpeg = QLineEdit(str(FFmpegManager.find_executable() or ""))
        ff_layout.addWidget(self._ffmpeg, 1)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse)
        ff_layout.addWidget(browse)
        form.addRow("FFmpeg 路径:", ff_layout)
        ok, msg = FFmpegManager.check_available(self._ffmpeg.text() or None)
        status = QLabel(f"{'✓ ' + msg if ok else '✗ ' + msg}")
        status.setStyleSheet(f"color: {'#22c55e' if ok else '#ef4444'}; font-size: 11px;")
        form.addRow("", status)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择 FFmpeg")
        if path: self._ffmpeg.setText(path)

    def _save(self):
        self._config.storage_mode = self._mode.currentData()
        self._config.storage_format = self._fmt.currentData()
        self._config.dedup = self._dedup.isChecked()
        ConfigManager.save(self._config)
        self.accept()
