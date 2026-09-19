"""平台主题横幅。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget


class HeroPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeroPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(140)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(self.rect(), 8, 8)
        painter.setClipPath(clip)
        app = QApplication.instance()
        is_dark = True if app is None else bool(app.property("darkTheme"))
        overlay = QLinearGradient(0, 0, self.width(), 0)
        if is_dark:
            overlay.setColorAt(0.0, QColor(12, 10, 30, 244))
            overlay.setColorAt(0.62, QColor(32, 17, 66, 218))
            overlay.setColorAt(1.0, QColor(9, 11, 28, 165))
        else:
            overlay.setColorAt(0.0, QColor(250, 248, 252, 244))
            overlay.setColorAt(0.62, QColor(247, 239, 249, 224))
            overlay.setColorAt(1.0, QColor(235, 244, 249, 194))
        painter.fillRect(self.rect(), overlay)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 95, 162, 42 if is_dark else 34))
        painter.drawEllipse(self.width() - 170, -62, 230, 230)
        painter.setBrush(QColor(98, 213, 255, 34 if is_dark else 42))
        painter.drawEllipse(self.width() - 300, 92, 190, 190)
        painter.end()
        super().paintEvent(event)
