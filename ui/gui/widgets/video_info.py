"""解析结果卡片。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class VideoInfoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(6)
        self._title_label = QLabel("作品资料卡")
        header.addWidget(self._title_label)
        self._state = QLabel("(等待解析)")
        self._state.setObjectName("Caption")
        header.addWidget(self._state)
        header.addStretch()
        layout.addLayout(header)
        self._info = QLabel("输入链接后点击 解析预览 查看作品信息")
        self._info.setWordWrap(True)
        self._info.setStyleSheet("color: #64748b;")
        layout.addWidget(self._info)
        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setVisible(False)
        layout.addWidget(self._detail)

    def show_work(self, work):
        self._state.setText("(已解析)")
        self._state.setStyleSheet("color: #22c55e; font-weight: bold;")
        lines = [
            f"标题: {work.get('title', '')}",
            f"作者: {work.get('author_name', '')}",
            f"平台: {work.get('platform', '')}",
        ]
        if work.get('digg_count'): lines.append(f"点赞: {work['digg_count']}")
        if work.get('comment_count'): lines.append(f"评论: {work['comment_count']}")
        if work.get('video_url'): lines.append(f"视频地址: {work['video_url'][:80]}...")
        if work.get('image_urls'): lines.append(f"图片: {len(work['image_urls'])} 张")
        self._detail.setText("\n".join(lines))
        self._detail.setVisible(True)
        self._info.setVisible(False)

    def show_empty(self):
        self._state.setText("(等待解析)")
        self._state.setStyleSheet("color: #64748b;")
        self._detail.setVisible(False)
        self._info.setVisible(True)

    def show_error(self, msg):
        self._state.setText("(解析失败)")
        self._state.setStyleSheet("color: #ef4444; font-weight: bold;")
        self._info.setText(msg)
        self._info.setVisible(True)
        self._detail.setVisible(False)
