from playwright.async_api import async_playwright

from core.config import Config, load_config

LAZY_LOAD_JS = """
() => {
    const imgs = document.querySelectorAll('img');
    imgs.forEach(img => {
        const dataSrc = img.getAttribute('data-src') || img.getAttribute('data-original');
        if (dataSrc && (!img.src || img.src.startsWith('data:'))) {
            img.src = dataSrc;
            img.removeAttribute('data-src');
        }
    });
    const bgEls = document.querySelectorAll('[data-background], [data-bg]');
    bgEls.forEach(el => {
        const bg = el.getAttribute('data-background') || el.getAttribute('data-bg');
        if (bg) el.style.backgroundImage = `url(${bg})`;
    });
}
"""


class WechatScraper:

    def __init__(self, config: Config | None = None):
        self._config = config or load_config()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self):
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=self._config.playwright_launch_args,
        )
        self._context = await self._browser.new_context(
            user_agent=self._config.user_agent,
            viewport={"width": 390, "height": 844},
        )
        self._page = await self._context.new_page()

    async def scrape(self, url: str) -> str:
        await self._ensure_browser()
        await self._page.goto(url, wait_until="networkidle", timeout=30000)
        await self._page.wait_for_timeout(1500)
        await self._page.evaluate(LAZY_LOAD_JS)
        await self._page.wait_for_timeout(500)
        return await self._page.content()

    async def get_title(self) -> str:
        if self._page is None:
            return "Unknown"
        try:
            title = await self._page.evaluate(
                "() => document.querySelector('#activity-name')?.textContent?.trim() || document.title"
            )
            return title or "Unknown"
        except Exception:
            return "Unknown"

    async def get_author(self) -> str:
        if self._page is None:
            return ""
        try:
            author = await self._page.evaluate(
                "() => document.querySelector('#js_name')?.textContent?.trim() || ''"
            )
            return author
        except Exception:
            return ""

    async def get_publish_date(self) -> str:
        if self._page is None:
            return ""
        try:
            date = await self._page.evaluate(
                "() => document.querySelector('#publish_time')?.textContent?.trim() || ''"
            )
            return date
        except Exception:
            return ""

    async def close(self):
        async def _safe_close(obj, method="close"):
            try:
                if obj is not None:
                    await getattr(obj, method)()
            except Exception:
                pass
        await _safe_close(self._page)
        await _safe_close(self._context)
        await _safe_close(self._browser)
        await _safe_close(self._playwright, "stop")
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
