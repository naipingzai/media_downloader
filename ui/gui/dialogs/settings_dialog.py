"""设置对话框。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout,
)
from shared.core.config import ConfigManager
from shared.core.ffmpeg import FFmpegManager


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
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

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("直接存储", "flat")
        self._mode_combo.addItem("按作者分目录", "by_author")
        self._mode_combo.addItem("按日期分目录", "by_date")
        self._mode_combo.addItem("按类型分目录", "by_type")
        idx = self._mode_combo.findData(self._config.storage_mode)
        if idx >= 0: self._mode_combo.setCurrentIndex(idx)
        form.addRow("存储模式:", self._mode_combo)

        self._fmt_combo = QComboBox()
        self._fmt_combo.addItem("JSON", "json")
        self._fmt_combo.addItem("CSV", "csv")
        idx = self._fmt_combo.findData(self._config.storage_format)
        if idx >= 0: self._fmt_combo.setCurrentIndex(idx)
        form.addRow("数据格式:", self._fmt_combo)

        self._dedup = QCheckBox("启用去重")
        self._dedup.setChecked(self._config.dedup)
        form.addRow("", self._dedup)

        layout.addLayout(form)

        ff_layout = QHBoxLayout()
        self._ffmpeg_path = QLineEdit(FFmpegManager.find_executable() and str(FFmpegManager.find_executable()) or "")
        ff_layout.addWidget(self._ffmpeg_path, 1)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_ffmpeg)
        ff_layout.addWidget(browse)
        form.addRow("FFmpeg 路径:", ff_layout)
        ok, msg = FFmpegManager.check_available(self._ffmpeg_path.text() or None)
        status = QLabel(f"{'✓ ' + msg if ok else '✗ ' + msg}")
        status.setStyleSheet(f"color: {'#22c55e' if ok else '#ef4444'}; font-size: 11px;")
        form.addRow("", status)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_ffmpeg(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择 FFmpeg")
        if path:
            self._ffmpeg_path.setText(path)

    def _save(self):
        self._config.storage_mode = self._mode_combo.currentData()
        self._config.storage_format = self._fmt_combo.currentData()
        self._config.dedup = self._dedup.isChecked()
        ConfigManager.save(self._config)
        self.accept()
