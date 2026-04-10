"""
Shared HTTP client using Playwright (headless Chrome):

  1. Real browser engine — solves eBay's Argon2 proof-of-work
     challenge automatically (no CAPTCHA bypass hacks needed)
  2. Per-request User-Agent rotation from the configured pool
  3. tenacity retry with exponential backoff on 429, 503, errors
  4. Soft-ban detection — raises SoftBanError before wasting time
  5. Warm-up request to establish cookies before real scraping

Why Playwright instead of aiohttp / curl_cffi?
  eBay serves a JavaScript proof-of-work challenge page
  ("Pardon Our Interruption") that computes an Argon2 hash
  before redirecting to the real content. Neither aiohttp nor
  curl_cffi can execute JavaScript, so they get stuck on the
  challenge page forever. Playwright runs real Chromium and
  solves the challenge transparently.
"""

import asyncio
import logging
import random

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Error as PlaywrightError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    BACKOFF_MAX, BACKOFF_MIN, MAX_RETRIES, USER_AGENTS
)
from utils import is_soft_banned

logger = logging.getLogger(__name__)

#=======================================================================
# EXCEPTIONS
#=======================================================================

class RateLimitError(Exception):
    """
    Raised when eBay returns HTTP 429 or 503.

    Signals tenacity to back off and retry.
    Do not catch this yourself inside fetch().
    """


class SoftBanError(Exception):
    """
    Raised when the response body contains a CAPTCHA signal.

    Unlike RateLimitError, this is NOT retried — the caller should
    skip the brand and log a warning rather than retrying a blocked
    session.
    """

#=======================================================================
# SESSION (BROWSER WRAPPER)
#=======================================================================

class BrowserSession:
    """
    Wraps a Playwright browser + context as an async context manager.

    Usage (always use as async context manager for cleanup):
        async with build_session() as session:
            html = await fetch(session, url)

    Internally launches headless Chromium, creates a browser context
    with a realistic user-agent, and exposes a single reusable page.
    """

    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
        )
        self._context = await self._browser.new_context(
            user_agent=random.choice(USER_AGENTS),
        )
        self.page = await self._context.new_page()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()


def build_session() -> BrowserSession:
    """
    Create a BrowserSession (headless Chromium).

    Usage (always use as async context manager for cleanup):
        async with build_session() as session:
            html = await fetch(session, url)

    The browser context persists cookies across navigations,
    just like a real browsing session.
    """
    return BrowserSession()

#=======================================================================
# WARM-UP
#=======================================================================

async def warm_up(session: BrowserSession) -> None:
    """
    Navigate to eBay's homepage before real scraping begins.

    Why this matters:
      A real browser never jumps straight to a deep search URL.
      It first visits the homepage, picks up cookies (session ID,
      tracking tokens), and only then navigates to search results.
      Skipping this step is one of the clearest bot signals.

    Playwright handles the full page lifecycle — JavaScript
    execution, cookie storage, redirects — automatically.
    """
    logger.info("Warm-up: visiting eBay homepage")
    try:
        await session.page.goto(
            "https://www.ebay.com/",
            wait_until="domcontentloaded",
        )
        cookies = await session._context.cookies()
        logger.info(
            "Warm-up complete — %d cookies stored",
            len(cookies),
        )
    except PlaywrightError as exc:
        logger.warning("Warm-up request failed: %s", exc)

    # Pause briefly — no real user clicks a link instantly
    await asyncio.sleep(random.uniform(2.0, 4.0))

#=======================================================================
# FETCH
#=======================================================================

@retry(
    # Retry on rate-limit responses AND transient browser errors.
    # SoftBanError is intentionally excluded — no point retrying
    # CAPTCHA.
    retry=(
        retry_if_exception_type(RateLimitError)
        | retry_if_exception_type(PlaywrightError)
    ),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(
        multiplier=1, min=BACKOFF_MIN, max=BACKOFF_MAX
    ),
    # Log a warning each time tenacity waits before a retry.
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,  # re-raise final exception if all retries exhausted
)
async def fetch(session: BrowserSession, url: str) -> str:
    """
    Navigate to a URL and return the page content as a string.

    Playwright handles eBay's JS proof-of-work challenge
    transparently — the page loads, JavaScript executes the
    Argon2 computation, the form auto-submits, and we get
    the real content after networkidle.

    Args:
        session: A BrowserSession (from build_session()).
        url:     The URL to navigate to.

    Returns:
        Page HTML as a Unicode string.

    Raises:
        RateLimitError:  HTTP 429 or 503 (after retries exhausted).
        SoftBanError:    CAPTCHA / challenge page detected.
        PlaywrightError: Persistent browser/network failure.
    """
    logger.debug("GET %s", url)

    response = await session.page.goto(url, wait_until="domcontentloaded")

    # Wait for any JS challenges to resolve and network to settle
    await session.page.wait_for_load_state(
        "networkidle", timeout=30000
    )

    status = response.status if response else 0

    if status in (429, 503):
        logger.warning(
            "Rate limit hit (HTTP %d) → tenacity will back off",
            status
        )
        raise RateLimitError(f"HTTP {status} from eBay")

    if status != 200 and status != 0:
        logger.warning(
            "Unexpected HTTP %d for %s — returning empty string",
            status,
            url
        )
        return ""

    html = await session.page.content()

    if is_soft_banned(html):
        raise SoftBanError(
            f"Soft-ban / CAPTCHA page detected at {url}"
        )

    return html
