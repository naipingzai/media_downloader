"""TUI App."""
from textual.app import App
from textual.binding import Binding
from shared.core import PROJECT_NAME
from shared.translation import _
from .screens.index import IndexScreen

class MediaDownloaderTUI(App):
    css_path = []
    TITLE = PROJECT_NAME
    BINDINGS = [Binding(key="q", action="quit", description="退出")]
    async def on_mount(self):
        self.theme = "nord"
        self.install_screen(IndexScreen(), name="index")
        await self.push_screen("index")
    async def action_quit(self): await self.app.action_quit()
