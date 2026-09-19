"""国际化翻译管理。"""
import sys
from gettext import translation
from locale import getlocale
from pathlib import Path

ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent.parent
)


class TranslationManager:
    """管理 gettext 翻译的单例。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, domain: str = "media", localedir: str | None = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.domain = domain
        self.localedir = Path(localedir) if localedir else ROOT / "locale"
        self.current_translator = self.setup_translation(self._get_language_code())

    @staticmethod
    def _get_language_code() -> str:
        language_code, __ = getlocale()
        if not language_code:
            return "en_US"
        return (
            "zh_CN"
            if any(s in language_code.upper() for s in ("CHINESE", "ZH", "CHINA"))
            else "en_US"
        )

    def setup_translation(self, language: str = "zh_CN"):
        try:
            return translation(
                self.domain, localedir=self.localedir, languages=[language], fallback=True
            )
        except FileNotFoundError:
            return translation(self.domain, fallback=True)

    def switch_language(self, language: str = "en_US"):
        self.current_translator = self.setup_translation(language)

    def gettext(self, message: str) -> str:
        return self.current_translator.gettext(message)


_translation_manager = TranslationManager()


def _translate(message: str) -> str:
    return _translation_manager.gettext(message)


def switch_language(language: str = "en_US"):
    global _
    _translation_manager.switch_language(language)
    _ = _translation_manager.gettext


_ = _translate
