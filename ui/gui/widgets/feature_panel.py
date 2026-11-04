"""功能面板 — 三组按钮, 网格按可用宽度自适应列数。

布局规则:
  - 每组一个 QGridLayout, 列数随面板宽度在 2~3 之间自适应
    (窄窗口 2 列避免按钮文字被挤压, 宽窗口 3 列更紧凑)。
  - 固有按钮在前, 平台按钮紧随其后连续填充。
  - 平台切换时整组重建 → 无叠加; 各平台网格结构/间距完全相同。
样式由主题 QSS 提供 (`#FeatureBtn` / `#FeatureGhostBtn` / `#FeatureStopBtn`)。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

LIVE_FEATURES = {"live", "tk_live"}

_MIN_COLS = 2
_MAX_COLS = 3
_COL_WIDTH = 180   # 单列最小舒适宽度 (px): 宽窗口 3 列, 常规/窄窗口 2 列


class FeatureGroup(QFrame):
    """功能分组框 — 带边框 + 左上标题 + 自适应列数网格。"""

    def __init__(self, title: str, cols: int = _MAX_COLS, parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureGroup")
        # 允许滚动容器按可用宽度压缩，最小宽度由自适应列数决定。
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self._MAX_COLS = max(cols, _MIN_COLS)
        self._cols = self._MAX_COLS
        self._items: list[tuple[QPushButton, bool]] = []
        self._base_count = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)
        lbl = QLabel(title)
        lbl.setObjectName("FeatureGroupTitle")
        outer.addWidget(lbl)

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(6)
        for i in range(self._MAX_COLS):
            self._grid.setColumnStretch(i, 1)
        outer.addLayout(self._grid)

    # ---------------- 填充 ----------------

    def set_buttons(self, base, platform, ghost: bool = False):
        """整组重建: base 固有按钮在前, platform 平台按钮紧随。"""
        self._clear()
        items = list(base) + list(platform)
        self._base_count = len(base)
        for text, slot in items:
            btn = self._new_btn(text, slot, ghost)
            self._items.append((btn, ghost))
        self._relayout()

    def _clear(self):
        while self._grid.count():
            it = self._grid.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._items.clear()

    @staticmethod
    def _new_btn(text: str, slot, ghost: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("FeatureGhostBtn" if ghost else "FeatureBtn")
        btn.setCursor(Qt.PointingHandCursor)
        # 按钮可随网格列宽压缩；长文本通过两列布局保证可读性。
        btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        btn.setMinimumWidth(0)
        # 最小高度按字体度量 (动态适应字号/DPI, 防文字裁剪)
        btn.setMinimumHeight(max(30, int(btn.fontMetrics().height() * 2.0)))
        btn.clicked.connect(lambda _checked=False, s=slot: s())
        return btn

    # ---------------- 自适应列数 ----------------

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        avail = max(1, self.width() - 20)
        want = max(_MIN_COLS, min(self._MAX_COLS, avail // _COL_WIDTH))
        if want != self._cols:
            self._cols = want
            self._relayout()

    def _relayout(self):
        for btn, _ghost in self._items:
            self._grid.removeWidget(btn)
        for i, (btn, _ghost) in enumerate(self._items):
            self._grid.addWidget(btn, i // self._cols, i % self._cols)
        for i in range(self._MAX_COLS):
            self._grid.setColumnStretch(i, 1 if i < self._cols else 0)

    def set_enabled(self, v: bool):
        """仅控制固有按钮 (平台按钮独立运行)。"""
        for b, _ghost in self._items[:self._base_count]:
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
        # 作为滚动内容时宽度完全跟随 viewport，避免产生横向滚动条。
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
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
        self._stop_btn.setObjectName("FeatureStopBtn")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setMinimumHeight(
            max(30, int(self._stop_btn.fontMetrics().height() * 2.0)))
        self._stop_btn.clicked.connect(self._on_stop)
        grid = self._feat_group.grid()
        n = grid.count()
        cols = self._feat_group._cols
        grid.addWidget(self._stop_btn, n // cols, n % cols)

    def _on_stop(self):
        self._recording = False
        if self._stop_btn:
            self._stop_btn.setParent(None)
            self._stop_btn.deleteLater()
            self._stop_btn = None
        self.stop_recording_clicked.emit()
