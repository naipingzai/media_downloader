"""Bilibili QR code login."""
import httpx
import qrcode
from io import BytesIO
from PIL import Image
from shared.core.login import PlatformLoginManager, LoginBus

PASSPORT_URL = "https://passport.bilibili.com"
QR_GENERATE = "/x/passport-login/web/qrcode/generate"
QR_POLL = "/x/passport-login/web/qrcode/poll"
NAV = "https://api.bilibili.com/x/web-interface/nav"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


class BilibiliLoginManager(PlatformLoginManager):
    platform_id = "bilibili"
    login_methods = ["qr"]

    def __init__(self):
        self._client = httpx.Client(
            base_url=PASSPORT_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=False,
        )

    def generate_qr(self) -> tuple[str, str, Image.Image]:
        resp = self._client.get(QR_GENERATE)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"QR failed: {data.get('message')}")
        url = data["data"]["url"]
        key = data["data"]["qrcode_key"]
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return url, key, img

    def check_qr_status(self, qrcode_key: str) -> dict:
        resp = self._client.get(QR_POLL, params={"qrcode_key": qrcode_key})
        resp.raise_for_status()
        data = resp.json()
        code = data.get("data", {}).get("code", -1)
        result = {"status": code}
        if code == 0:
            result["code"] = 0
            sessdata = self._find_cookie(resp.cookies, "SESSDATA")
            if not sessdata:
                sessdata = self._find_cookie(self._client.cookies, "SESSDATA")
            if sessdata:
                result["cookies"] = {"SESSDATA": sessdata}
                return result
            sso_url = data.get("data", {}).get("url", "")
            result["cookies"] = self._extract_from_sso(sso_url)
        return result

    def _extract_from_sso(self, sso_url: str) -> dict:
        if not sso_url:
            return {}
        try:
            with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=False) as c:
                url = sso_url
                for _ in range(10):
                    r = c.get(url)
                    if not r.is_redirect: break
                    loc = r.headers.get("location", "")
                    if not loc: break
                    url = loc if loc.startswith("http") else f"https:{loc}"
                sd = self._find_cookie(c.cookies, "SESSDATA")
                if sd: return {"SESSDATA": sd}
        except Exception:
            pass
        return {}

    def validate(self, sessdata: str) -> bool:
        try:
            r = httpx.get(NAV, cookies={"SESSDATA": sessdata},
                         headers={"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com/"},
                         timeout=10.0)
            return r.json().get("data", {}).get("isLogin", False)
        except Exception:
            return False

    @staticmethod
    def _find_cookie(cookies, name):
        for c in cookies.jar:
            if c.name == name and c.value:
                return c.value
        return None

    def close(self):
        self._client.close()
