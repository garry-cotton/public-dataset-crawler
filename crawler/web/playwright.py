from typing import Optional

from dataclass import HtmlPage
from config import Defaults, Defaults

class PlaywrightRenderer:
    def __init__(
            self,
            enabled: bool,
            browser: str = "chromium",
            wait_ms: int = 2500,
            headless: bool = True) -> None:
        
        self.enabled = enabled
        self.browser_name = browser
        self.wait_ms = wait_ms
        self.headless = headless
        self._playwright = None
        self._browser = None

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure_browser(self) -> bool:
        if not self.enabled:
            return False
        if self._browser is not None:
            return True

        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            browser_launcher = getattr(self._playwright, self.browser_name)
            self._browser = browser_launcher.launch(headless=self.headless)
            return True
        except Exception:
            self.close()
            return False

    def fetch(self, url: str) -> Optional[HtmlPage]:
        if not self._ensure_browser():
            return None

        context = None
        page = None
        try:
            context = self._browser.new_context(user_agent=Defaults.user_agent)
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=Defaults.request_timeout * 1000)
            if self.wait_ms > 0:
                page.wait_for_timeout(self.wait_ms)
            html = page.content()
            final_url = page.url
            return HtmlPage(url=final_url, html=html, fetched_via="playwright")
        except Exception:
            return None
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
