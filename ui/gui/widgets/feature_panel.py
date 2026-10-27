"""功能面板 — 三个分组框, 单一网格连续排布 (固有+平台按钮统一布局)。

布局规则 (所有平台一致):
  每组一个 QGridLayout, 3 列; 固有按钮在前, 平台按钮紧随其后连续填充。
  平台切换时整组重建 → 无叠加; 各平台网格结构/间距完全相同。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

LIVE_FEATURES = {"live", "tk_live"}

_BTN_STYLE = (
    "QPushButton { background: #1d4ed8; color: white; border: none;"
    " border-radius: 6px; padding: 6px 6px; font-size: 14px;"
    " font-weight: bold; }"
    "QPushButton:hover { background: #2563eb; }"
    "QPushButton:disabled { background: #334155; color: #64748b; }")
_GHOST_STYLE = (
    "QPushButton { background: transparent; color: #cbd5e1;"
    " border: 1px solid #334155; border-radius: 6px;"
    " padding: 6px 6px; font-size: 14px; font-weight: bold; }"
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
    """功能分组框 — 带边框 + 左上标题 + 单一 3 列网格。

    set_buttons(base, platform) 整组重建:
    固有按钮 + 平台按钮在同一网格连续排布 → 各平台间距/结构一致。
    """

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

    def set_buttons(self, base, platform, ghost: bool = False):
        """整组重建: base 固有按钮在前, platform 平台按钮紧随, 连续 3 列。"""
        self._clear()
        self._base_btns.clear()
        i = 0
        for text, slot in base:
            btn = self._new_btn(text, slot, ghost)
            self._base_btns.append(btn)
            self._grid.addWidget(btn, i // self._COLS, i % self._COLS)
            i += 1
        for text, slot in platform:
            btn = self._new_btn(text, slot, ghost)
            self._grid.addWidget(btn, i // self._COLS, i % self._COLS)
            i += 1

    def _clear(self):
        while self._grid.count():
            it = self._grid.takeAt(0)
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
        self._base_work = list(work_buttons or [])
        self._base_author = list(author_buttons or [])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        self._work_group = FeatureGroup("作品操作")
        self._work_group.set_buttons(self._base_work, [])
        outer.addWidget(self._work_group)
        self._work_group.set_enabled(False)
        self._author_group = FeatureGroup("作者操作")
        self._author_group.set_buttons(self._base_author, [], ghost=True)
        outer.addWidget(self._author_group)
        self._feat_group = FeatureGroup("平台功能")
        outer.addWidget(self._feat_group)
        outer.addStretch()

    def set_features(self, features):
        """按 FeatureMeta.group 分发到各组, 整组重建 (固有+平台连续排布)。

        work → 作品操作组; user → 作者操作组; platform → 平台功能组。
        """
        groups: dict[str, list] = {"work": [], "user": [], "platform": []}
        for f in features or []:
            g = getattr(f, "group", "platform") or "platform"
            groups.setdefault(g, []).append(
                (f.name, (lambda fid=f.id: self._on_click(fid))))
        self._work_group.set_buttons(self._base_work, groups.get("work", []))
        self._author_group.set_buttons(
            self._base_author, groups.get("user", []), ghost=True)
        self._feat_group.set_buttons([], groups.get("platform", []))
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
            " border-radius: 6px; padding: 6px 6px; font-size: 14px;"
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
