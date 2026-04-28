"""ORBITRA CORE — async Playwright crawler with browser pool, stealth, and retry."""

import asyncio
import random
import time
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin, urlunparse, urlencode, parse_qsl

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, PlaywrightContextManager
from config import (
    USER_AGENTS, CRAWL_TIMEOUT, PAGE_LOAD_TIMEOUT, NETWORK_IDLE_TIMEOUT,
    MAX_RETRIES, BLOCKED_RESOURCE_TYPES, BLOCKED_DOMAINS, ConcurrencyProfile
)

log = logging.getLogger("orbitra.crawler")


@dataclass
class FetchResult:
    url: str
    html: str
    final_url: str
    status: int
    elapsed: float
    error: str | None = None
    ok: bool = True


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # Sort query params, strip fragment
    query = urlencode(sorted(parse_qsl(parsed.query)))
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", query, ""))
    return normalized


def is_blocked_domain(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(blocked in host for blocked in BLOCKED_DOMAINS)


async def _stealth_patch(context: BrowserContext) -> None:
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({query: () => Promise.resolve({state: 'granted'})})
        });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (params) =>
            params.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : originalQuery(params);
    """)


class BrowserPool:
    def __init__(self, profile: ConcurrencyProfile):
        self.profile = profile
        self._playwright: PlaywrightContextManager | None = None
        self._pw = None
        self._browsers: list[Browser] = []
        self._semaphore = asyncio.Semaphore(profile.max_pages)
        self._browser_idx = 0
        self._lock = asyncio.Lock()

    async def start(self):
        self._playwright = async_playwright()
        self._pw = await self._playwright.__aenter__()
        for _ in range(self.profile.max_browsers):
            browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1366,768",
                ]
            )
            self._browsers.append(browser)
        log.info(f"Browser pool started: {self.profile.max_browsers} browsers, {self.profile.max_pages} max pages")

    async def stop(self):
        for browser in self._browsers:
            await browser.close()
        if self._playwright:
            await self._playwright.__aexit__(None, None, None)
        log.info("Browser pool stopped")

    def _next_browser(self) -> Browser:
        browser = self._browsers[self._browser_idx % len(self._browsers)]
        self._browser_idx += 1
        return browser

    async def fetch(self, url: str) -> FetchResult:
        async with self._semaphore:
            return await self._fetch_with_retry(url)

    async def _fetch_with_retry(self, url: str) -> FetchResult:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = await asyncio.wait_for(
                    self._do_fetch(url),
                    timeout=CRAWL_TIMEOUT
                )
                if result.ok:
                    return result
                # Don't retry 404
                if result.status == 404:
                    return result
                # Backoff for 429
                if result.status == 429:
                    wait = 4 ** attempt
                    log.warning(f"Rate limited {url}, waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue
                last_error = result.error
            except asyncio.TimeoutError:
                last_error = "timeout"
                log.warning(f"Timeout on {url} attempt {attempt+1}")
            except Exception as e:
                last_error = str(e)
                # TargetClosedError and similar browser crashes — don't retry
                if "TargetClosedError" in type(e).__name__ or "closed" in str(e).lower():
                    log.warning(f"Browser closed on {url} — skipping")
                    break
                log.warning(f"Error on {url} attempt {attempt+1}: {e}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(4 ** attempt)

        return FetchResult(url=url, html="", final_url=url, status=0,
                           elapsed=0, error=last_error, ok=False)

    async def _do_fetch(self, url: str) -> FetchResult:
        browser = self._next_browser()
        ua = random.choice(USER_AGENTS)
        context: BrowserContext = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await _stealth_patch(context)

        page: Page = await context.new_page()

        # Block unwanted resources
        async def handle_route(route):
            rt = route.request.resource_type
            req_url = route.request.url
            if rt in BLOCKED_RESOURCE_TYPES or is_blocked_domain(req_url):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", handle_route)

        start = time.time()
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PAGE_LOAD_TIMEOUT
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
            except Exception:
                pass  # networkidle timeout is OK

            status = response.status if response else 0
            html = await page.content()
            final_url = page.url
            elapsed = time.time() - start

            ok = status < 400 and bool(html)
            return FetchResult(
                url=url, html=html, final_url=final_url,
                status=status, elapsed=elapsed, ok=ok,
                error=None if ok else f"HTTP {status}"
            )
        except Exception as e:
            return FetchResult(
                url=url, html="", final_url=url,
                status=0, elapsed=time.time() - start,
                error=str(e), ok=False
            )
        finally:
            await page.close()
            await context.close()

            # Request delay
            if self.profile.request_delay > 0:
                await asyncio.sleep(self.profile.request_delay)


class Crawler:
    def __init__(self, profile: ConcurrencyProfile):
        self.pool = BrowserPool(profile)
        self._seen: set[str] = set()
        self._domain_counts: dict[str, int] = {}

    async def __aenter__(self):
        await self.pool.start()
        return self

    async def __aexit__(self, *args):
        await self.pool.stop()

    def is_seen(self, url: str) -> bool:
        norm = normalize_url(url)
        return norm in self._seen

    def mark_seen(self, url: str) -> None:
        self._seen.add(normalize_url(url))

    def domain_count(self, url: str) -> int:
        domain = urlparse(url).netloc
        return self._domain_counts.get(domain, 0)

    def increment_domain(self, url: str) -> None:
        domain = urlparse(url).netloc
        self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1

    async def fetch(self, url: str) -> FetchResult:
        self.mark_seen(url)
        self.increment_domain(url)
        return await self.pool.fetch(url)

    def extract_links(self, base_url: str, html: str) -> list[tuple[str, str]]:
        """Extract (url, anchor_text) from HTML. Pure string parsing — no BS4 needed here,
        extractor.py handles full parse; this is a fast pre-pass."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        links = []
        base_domain = urlparse(base_url).netloc

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            anchor = a.get_text(strip=True)[:200]
            try:
                full = urljoin(base_url, href)
                parsed = urlparse(full)
                if parsed.scheme not in ("http", "https"):
                    continue
                # Only same-domain or explicit off-domain (graph tracks both)
                links.append((full, anchor))
            except Exception:
                continue
        return links
