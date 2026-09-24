"""功能面板 — 每个模块独立带边框分组框 (GroupBox 风格), 按钮网格对齐。

模块:
  作品操作  (获取链接/查看评论/下载封面 …, 依赖当前作品)
  作者操作  (获取作品/关注列表/收藏列表/下载头像/获取主页)
  平台功能  (下载/批量/合集 …, 随平台切换)
"""
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

_GROUP_STYLE = (
    "QFrame#FeatureGroup { background: #1e293b;"
    " border: 1px solid #334155; border-radius: 6px; }")

_TITLE_STYLE = (
    "color: #94a3b8; font-size: 14px; font-weight: bold;"
    " background: transparent; border: none; padding: 0;")


class FeatureGroup(QFrame):
    """功能分组框 — 带边框 + 左上标题 + 3 列按钮网格。"""

    def __init__(self, title: str, cols: int = 3, parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureGroup")
        self.setStyleSheet(_GROUP_STYLE)
        self._COLS = cols
        self._btns: list[QPushButton] = []

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

    def set_buttons(self, btns):
        """填充按钮: [(文字, slot), ...]。"""
        # 清空旧按钮
        while self._grid.count():
            it = self._grid.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._btns.clear()
        for i, (text, slot) in enumerate(btns):
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setStyleSheet(_BTN_STYLE)
            btn.clicked.connect(lambda _checked=False, s=slot: s())
            self._btns.append(btn)
            self._grid.addWidget(btn, i // self._COLS, i % self._COLS)

    def set_enabled(self, v: bool):
        for b in self._btns:
            b.setEnabled(v)

    def grid(self) -> QGridLayout:
        return self._grid


class FeaturePanel(QWidget):
    """功能面板 — 三个独立分组框纵向排列。"""

    execute_clicked = Signal(str, str, dict)   # (feature_id, url, opts)
    stop_recording_clicked = Signal()

    def __init__(self, parent=None, work_buttons=None, author_buttons=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("FeaturePanel { background: transparent; }")
        self._recording = False
        self._feat_btns: dict = {}
        self._stop_btn = None
        self._current_fid = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # 1) 作品操作 (无作品时禁用)
        self._work_group = FeatureGroup("作品操作")
        self._work_group.set_buttons(list(work_buttons or []))
        outer.addWidget(self._work_group)
        self._work_group.set_enabled(False)

        # 2) 作者操作
        self._author_group = FeatureGroup("作者操作")
        self._author_group.set_buttons(list(author_buttons or []))
        outer.addWidget(self._author_group)

        # 3) 平台功能 (随平台切换重建)
        self._feat_group = FeatureGroup("平台功能")
        outer.addWidget(self._feat_group)

        outer.addStretch()

    def set_features(self, features):
        """重建平台功能分组。"""
        btns = [(f.name, (lambda fid=f.id: self._on_click(fid))) for f in features]
        self._feat_group.set_buttons(btns)
        # 记录 fid → 按钮 (录制状态联动)
        self._feat_btns = {}
        for (name, _slot), btn in zip(btns, self._feat_group._btns):
            pass  # fid 映射在 _on_click 中通过 lambda 捕获, 这里仅重建
        self._stop_btn = None
        self._recording = False

    # ===== 作品可用性 =====
    def set_work_available(self, available: bool):
        self._work_group.set_enabled(available)

    # ===== 录制状态 (直播类功能) =====
    def set_recording(self, recording: bool):
        self._recording = recording
        if self._stop_btn:
            self._stop_btn.setVisible(recording)
        # 录制中禁用平台功能组 (避免并发), 结束恢复
        for b in self._feat_group._btns:
            b.setEnabled(not recording or True)  # 保留可点其他功能, 直播按钮由 stop 控制

    def _on_click(self, fid: str):
        if fid in LIVE_FEATURES and self._recording:
            return
        self._current_fid = fid
        if fid in LIVE_FEATURES and not self._stop_btn:
            self._recording = True
            self._add_stop_btn()
            self._stop_btn.setVisible(True)
        opts = {"danmaku": True, "subtitle": True, "cover": True, "metadata": True}
        self.execute_clicked.emit(fid, "", opts)

    def _add_stop_btn(self):
        """停止按钮追加到平台功能网格末尾。"""
        self._stop_btn = QPushButton("停止录制")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setMinimumHeight(36)
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
