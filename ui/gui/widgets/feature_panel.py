"""功能面板 — 平台功能独立网格整体重建 (防切换平台按钮叠加)。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

LIVE_FEATURES = {"live", "tk_live"}

_BTN_STYLE = (
    "QPushButton { background: #1d4ed8; color: white; border: none;"
    " border-radius: 6px; padding: 8px 6px; font-size: 14px;"
    " font-weight: bold; }"
    "QPushButton:hover { background: #2563eb; }"
    "QPushButton:disabled { background: #334155; color: #64748b; }")
_GHOST_STYLE = (
    "QPushButton { background: transparent; color: #cbd5e1;"
    " border: 1px solid #334155; border-radius: 6px;"
    " padding: 8px 6px; font-size: 14px; font-weight: bold; }"
    "QPushButton:hover { background: #334155; border-color: #475569;"
    " color: #f1f5f9; }"
    "QPushButton:disabled { color: #475569; border-color: #334155; }")
_GROUP_STYLE = (
    "QFrame#FeatureGroup { background: #1e293b;"
    " border: 1px solid #334155; border-radius: 6px; }")
_TITLE_STYLE = (
    "color: #94a3b8; font-size: 14px; font-weight: bold;"
    " background: transparent; border: none; padding: 0;")


class FeatureGroup(QFrame):
    """功能分组框 — 带边框 + 左上标题 + 双段按钮网格 (固有区 + 平台区)。"""

    def __init__(self, title: str, cols: int = 3, parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureGroup")
        self.setStyleSheet(_GROUP_STYLE)
        self._COLS = cols
        self._base_btns: list[QPushButton] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(_TITLE_STYLE)
        outer.addWidget(lbl)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        for i in range(cols):
            self._grid.setColumnStretch(i, 1)
        outer.addLayout(self._grid)
        # 平台按钮网格 (整体重建, 防切换平台叠加)
        self._platform_grid = QGridLayout()
        self._platform_grid.setContentsMargins(0, 0, 0, 0)
        self._platform_grid.setSpacing(8)
        for i in range(cols):
            self._platform_grid.setColumnStretch(i, 1)
        outer.addLayout(self._platform_grid)

    def set_buttons(self, btns, ghost: bool = False):
        """填充固有按钮: [(文字, slot), ...]。"""
        self._clear(self._grid)
        self._base_btns.clear()
        for i, (text, slot) in enumerate(btns):
            btn = self._new_btn(text, slot, ghost)
            self._base_btns.append(btn)
            self._grid.addWidget(btn, i // self._COLS, i % self._COLS)

    def set_platform_buttons(self, btns, ghost: bool = False):
        """整体重建平台按钮区 (先清空再加 → 切换平台不叠加)。"""
        self._clear(self._platform_grid)
        for i, (text, slot) in enumerate(btns):
            btn = self._new_btn(text, slot, ghost)
            self._platform_grid.addWidget(btn, i // self._COLS, i % self._COLS)

    @staticmethod
    def _clear(grid: QGridLayout):
        while grid.count():
            it = grid.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    @staticmethod
    def _new_btn(text: str, slot, ghost: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        # 最小高度按字体度量 (2.1 倍字高), 随字号/DPI 弹性, 防文字裁剪
        btn.setMinimumHeight(max(32, int(btn.fontMetrics().height() * 2.1)))
        btn.setStyleSheet(_GHOST_STYLE if ghost else _BTN_STYLE)
        btn.clicked.connect(lambda _checked=False, s=slot: s())
        return btn

    def set_enabled(self, v: bool):
        """仅控制固有按钮 (平台按钮独立运行)。"""
        for b in self._base_btns:
            try:
                b.setEnabled(v)
            except RuntimeError:
                pass

    def grid(self) -> QGridLayout:
        return self._grid

    def platform_grid(self) -> QGridLayout:
        return self._platform_grid


class FeaturePanel(QWidget):
    """功能面板 — 三个分组框, 平台功能按 FeatureMeta.group 自动分发。"""

    execute_clicked = Signal(str, str, dict)
    stop_recording_clicked = Signal()

    def __init__(self, parent=None, work_buttons=None, author_buttons=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("FeaturePanel { background: transparent; }")
        self._recording = False
        self._stop_btn = None
        self._current_fid = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        self._work_group = FeatureGroup("作品操作")
        self._work_group.set_buttons(list(work_buttons or []))
        outer.addWidget(self._work_group)
        self._work_group.set_enabled(False)
        self._author_group = FeatureGroup("作者操作")
        self._author_group.set_buttons(list(author_buttons or []), ghost=True)
        outer.addWidget(self._author_group)
        self._feat_group = FeatureGroup("平台功能")
        outer.addWidget(self._feat_group)
        outer.addStretch()

    def set_features(self, features):
        """按 group 分发平台功能到各组平台区 (整体重建, 不叠加)。

        work → 作品操作平台区; user → 作者操作平台区;
        platform → 平台功能固有网格。
        """
        groups: dict[str, list] = {"work": [], "user": [], "platform": []}
        for f in features or []:
            g = getattr(f, "group", "platform") or "platform"
            groups.setdefault(g, []).append(
                (f.name, (lambda fid=f.id: self._on_click(fid))))
        self._work_group.set_platform_buttons(groups.get("work", []))
        self._author_group.set_platform_buttons(
            groups.get("user", []), ghost=True)
        self._feat_group.set_buttons(groups.get("platform", []))
        self._stop_btn = None
        self._recording = False

    def set_work_available(self, available: bool):
        self._work_group.set_enabled(available)

    def set_recording(self, recording: bool):
        self._recording = recording
        if self._stop_btn:
            self._stop_btn.setVisible(recording)

    def _on_click(self, fid: str):
        if fid in LIVE_FEATURES and self._recording:
            return
        self._current_fid = fid
        if fid in LIVE_FEATURES and not self._stop_btn:
            self._recording = True
            self._add_stop_btn()
            self._stop_btn.setVisible(True)
        opts = {"danmaku": True, "subtitle": True, "cover": True,
                "metadata": True}
        self.execute_clicked.emit(fid, "", opts)

    def _add_stop_btn(self):
        self._stop_btn = QPushButton("停止录制")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setMinimumHeight(
            max(32, int(self._stop_btn.fontMetrics().height() * 2.1)))
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #dc2626; color: white; border: none;"
            " border-radius: 6px; padding: 8px 6px; font-size: 14px;"
            " font-weight: bold; }"
            "QPushButton:hover { background: #ef4444; }")
        self._stop_btn.clicked.connect(self._on_stop)
        grid = self._feat_group.grid()
        n = grid.count()
        grid.addWidget(self._stop_btn, n // self._feat_group._COLS,
                       n % self._feat_group._COLS)

    def _on_stop(self):
        self._recording = False
        if self._stop_btn:
            self._stop_btn.setParent(None)
            self._stop_btn.deleteLater()
            self._stop_btn = None
        self.stop_recording_clicked.emit()
