"""自适应封面标签 — 按比例缩放、居中显示完整封面（不裁剪），随控件尺寸自动缩放。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

__all__ = ["CoverLabel"]

PLACEHOLDER_STYLE = (
    "background: #0f172a; color: #475569; border: 1px solid #334155;"
    " border-radius: 6px; font-size: 12px;")
LOADED_STYLE = "background: #0f172a; border-radius: 6px;"


class CoverLabel(QLabel):
    """封面显示控件：留白居中，随尺寸变化自适应重绘。"""

    def __init__(self, placeholder: str = "封面", parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self._placeholder = placeholder
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(96, 64)
        self.show_placeholder()

    def show_placeholder(self, text: str | None = None):
        """显示占位文字（封面/加载中/无封面）。"""
        if text is not None:
            self._placeholder = text
        self._pix = None
        self.setPixmap(QPixmap())
        self.setText(self._placeholder)
        self.setStyleSheet(PLACEHOLDER_STYLE)

    def set_source_pixmap(self, pix: QPixmap):
        """设置封面图并自适应缩放显示。"""
        self._pix = pix
        self.setText("")
        self.setStyleSheet(LOADED_STYLE)
        self._render()

    def _render(self):
        if self._pix is None or self._pix.isNull():
            return
        scaled = self._pix.scaled(self.size(), Qt.KeepAspectRatio,
                                  Qt.SmoothTransformation)
        super().setPixmap(scaled)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._render()
