"""
Shared aiohttp session factory with anti-ban measures:

  1. Browser-like headers injected on every request
  2. Per-request User-Agent rotation from the configured pool
  3. tenacity retry with exponential backoff on 429, 503, errors
  4. Soft-ban detection — raises SoftBanError before wasting time
"""

import logging
import random

import aiohttp
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    BACKOFF_MAX, BACKOFF_MIN, BASE_HEADERS, MAX_RETRIES, USER_AGENTS
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
# SESSION FACTORY
#=======================================================================

def build_session() -> aiohttp.ClientSession:
    """
    Create a shared aiohttp ClientSession with browser-like defaults.

    Usage (always use as async context manager for cleanup):
        async with build_session() as session:
            html = await fetch(session, url)

    The session persists cookies across requests within a run, which
    makes the traffic pattern look more like a real browsing session.
    """
    connector = aiohttp.TCPConnector(
        ssl=True,
        limit=10,          # max total open connections across all hosts
        limit_per_host=5,  # max concurrent connections to eBay
    )
    return aiohttp.ClientSession(
        connector=connector,
        headers=_fresh_headers(),
        timeout=aiohttp.ClientTimeout(total=30),
    )


def _fresh_headers() -> dict:
    """Return BASE_HEADERS with a randomly selected User-Agent."""
    headers = BASE_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers

#=======================================================================
# FETCH
#=======================================================================

@retry(
    # Retry on rate-limit responses AND transient network failures.
    # SoftBanError is intentionally excluded — no point retrying CAPTCHA.
    retry=(
        retry_if_exception_type(RateLimitError)
        | retry_if_exception_type(aiohttp.ClientError)
    ),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=BACKOFF_MIN, max=BACKOFF_MAX),
    # Log a warning each time tenacity waits before a retry.
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,  # re-raise final exception if all retries exhausted
)
async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    """
    Fetch a URL and return the response body as a string.

    Anti-ban measures applied on every call:
      - Rotates User-Agent header before each request
      - Raises RateLimitError on 429/503 → tenacity backs off
      - Raises SoftBanError on CAPTCHA → caller skips, no retry
      - Raises aiohttp.ClientError on network issues → tenacity retries

    Args:
        session: A shared aiohttp.ClientSession (from build_session()).
        url:     The URL to fetch.

    Returns:
        Response body as a Unicode string.

    Raises:
        RateLimitError:      HTTP 429 or 503 (after retries exhausted).
        SoftBanError:        CAPTCHA / challenge page detected.
        aiohttp.ClientError: Persistent network failure.
    """
    # Rotate UA on every individual request, not just per session
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    logger.debug("GET %s", url)

    async with session.get(url) as response:
        status = response.status

        if status in (429, 503):
            logger.warning(
                "Rate limit hit (HTTP %d) → tenacity will back off",
                status
            )
            raise RateLimitError(f"HTTP {status} from eBay")

        if status != 200:
            logger.warning(
                "Unexpected HTTP %d for %s — returning empty string",
                status,
                url
            )
            return ""

        html = await response.text()

        if is_soft_banned(html):
            raise SoftBanError(
                f"Soft-ban / CAPTCHA page detected at {url}"
            )

        return html
