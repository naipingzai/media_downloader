"""主题管理。"""
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, dark: bool = True):
    app.setProperty("darkTheme", dark)
    palette = QPalette()
    if dark:
        palette.setColor(QPalette.Window, QColor(15, 23, 42))
        palette.setColor(QPalette.WindowText, QColor(226, 232, 240))
        palette.setColor(QPalette.Base, QColor(30, 41, 59))
        palette.setColor(QPalette.Text, QColor(226, 232, 240))
        palette.setColor(QPalette.Button, QColor(51, 65, 85))
        palette.setColor(QPalette.ButtonText, QColor(226, 232, 240))
        palette.setColor(QPalette.Highlight, QColor(56, 189, 248))
        palette.setColor(QPalette.HighlightedText, QColor(15, 23, 42))
    else:
        palette.setColor(QPalette.Window, QColor(241, 245, 249))
        palette.setColor(QPalette.WindowText, QColor(15, 23, 42))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.Text, QColor(15, 23, 42))
        palette.setColor(QPalette.Button, QColor(226, 232, 240))
        palette.setColor(QPalette.ButtonText, QColor(15, 23, 42))
        palette.setColor(QPalette.Highlight, QColor(59, 130, 246))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
