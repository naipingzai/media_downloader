"""PySide6 GUI 启动器。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _find_check_icon() -> Path | None:
    """查找 checkbox 对勾图标 (兼容 PyInstaller 冻结)。"""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "static" / "checkbox_check.svg")
        candidates.append(Path(sys.argv[0]).resolve().parent
                          / "static" / "checkbox_check.svg")
    else:
        candidates.append(ROOT / "static" / "checkbox_check.svg")
    for p in candidates:
        if p.is_file():
            return p
    return None


def _apply_font(app, font_size: int):
    """全局字体设置。

    - pointSize (而非 pixelSize): 跟随系统 DPI 缩放, 用户改整体显示
      大小时所有组件/文字/图片/按钮等比例拉伸 (HiDPI 正确行为)。
    - 12~20 的配置值映射为 pointSize (约等于原 px 值的 0.75 倍)。
    """
    from PySide6.QtGui import QFont
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                      "Noto Sans CJK SC", "WenQuanYi Micro Hei",
                      "Source Han Sans CN"])
    # px → pt: 100% 缩放下 1pt ≈ 1.333px; clamp 到合理范围
    pt = max(9, min(16, round(font_size * 0.75)))
    font.setPointSize(pt)
    app.setFont(font)


def launch():
    # ---- HiDPI: 跟随系统缩放 (用户改显示大小 → 全 UI 等比拉伸) ----
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("请安装 PySide6: pip install PySide6")
        return
    # 必须在 QApplication 创建前设置缩放属性
    app = QApplication(sys.argv)
    app.setApplicationName("MediaDownloader")
    # 加载配置 → 应用字体
    from shared.core.config import ConfigManager
    cfg = ConfigManager.load()
    _apply_font(app, cfg.font_size)
    # 下载队列限速: 启动即应用持久化配置
    try:
        from shared.flow.queue import get_queue
        get_queue().set_speed_limit(int(getattr(cfg, "speed_limit", 0) or 0))
    except Exception:
        pass

    icon = _find_check_icon()
    icon_url = icon.as_posix() if icon else ""
    from .resources import theme as _theme
    _theme.set_check_icon_url(icon_url)
    _theme.apply_theme(app, "dark")

    from .main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
