"""
Stage 2 — BOLO Calculator

For each brand from Stage 1, fires two concurrent HTTP requests:
  - Request A (Sold):   sold listings last 90 days → count + avg price
  - Request B (Active): currently active listings → count

Anti-ban measures applied here:
  - asyncio.Semaphore(SEMAPHORE_LIMIT): max N brands in-flight
  - Per-brand jitter sleep after each pair of requests completes
  - All network calls go through http_client.fetch() (retry, UA)

Flow:
    brands: list[str]
        → [semaphore gate]
        → fetch sold + active (concurrent per brand)
        → jitter sleep
        → BrandResult dataclass
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, urlencode, urlparse, parse_qs

from bs4 import BeautifulSoup

from config import BASE_CATEGORY_URL, SEMAPHORE_LIMIT
from http_client import SoftBanError, fetch
from utils import random_jitter

logger = logging.getLogger(__name__)

#=======================================================================
# DATA TYPES
#=======================================================================

@dataclass
class BrandResult:
    """Raw scraped data for a single brand, before calculations."""
    brand: str
    category: str
    sold_90_days_count: int = 0
    active_listings_count: int = 0
    avg_sold_price: float = 0.0
    scrape_error: Optional[str] = None  # set if fetching/parsing failed

#=======================================================================
# URL BUILDERS
#=======================================================================

def _encode_brand(brand: str) -> str:
    """
    Double-encode a brand name for eBay's URL format.

    eBay's brand filter uses double URL-encoding:
      "L.L. Bean" → "L%2EL%2E%20Bean" → "L%252EL%252E%2520Bean"

    Standard urlencode produces "L.L.+Bean" which eBay silently
    ignores. We must match the encoding the LHN sidebar links
    use, including encoding dots (which RFC 3986 normally skips).
    """
    # First encode: spaces→%20, etc. (quote skips dots by default)
    single = quote(brand, safe="")
    # Manually encode dots — eBay requires %2E, not literal "."
    single = single.replace(".", "%2E")
    # Second encode: encode the % signs → %25
    return quote(single, safe="")


def _build_sold_url(
    brand: str, base_url: str = BASE_CATEGORY_URL
) -> str:
    """
    Build the sold-listings URL for a brand.

    Adds to the base category URL:
      - LH_Sold=1      → filter to sold items only
      - LH_Complete=1   → completed listings (required with Sold)
      - Brand=<name>    → double-encoded brand filter
      - _dcat=57990     → category context (required for Brand)

    Removes _sop (sort order) — irrelevant for sold listings.
    """
    params = parse_qs(
        urlparse(base_url).query, keep_blank_values=True
    )
    params["LH_Sold"] = ["1"]
    params["LH_Complete"] = ["1"]
    params["_dcat"] = ["57990"]
    params.pop("_sop", None)  # "sort: newly listed" not needed

    base = base_url.split("?")[0]
    qs = urlencode({k: v[0] for k, v in params.items()})
    return f"{base}?{qs}&Brand={_encode_brand(brand)}"


def _build_active_url(
    brand: str, base_url: str = BASE_CATEGORY_URL
) -> str:
    """
    Build the active-listings URL for a brand.

    Keeps all base filters intact (Pre-owned, BIN, $30+)
    and adds the double-encoded Brand filter + _dcat.
    """
    params = parse_qs(
        urlparse(base_url).query, keep_blank_values=True
    )
    params["_dcat"] = ["57990"]

    base = base_url.split("?")[0]
    qs = urlencode({k: v[0] for k, v in params.items()})
    return f"{base}?{qs}&Brand={_encode_brand(brand)}"

#=======================================================================
# HTML PARSERS
#=======================================================================

def _parse_listing_count(html: str) -> int:
    """
    Extract the total result count from an eBay search results page.

    eBay typically shows:
      <h1 class="srp-controls__count-heading">
          <span class="BOLD">91</span> results
      </h1>

    or in newer layouts:
      <span class="s-item__results-count">91 Results</span>

    Returns 0 if no count is found.
    """
    import re
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: srp-controls__count-heading (most common)
    heading = soup.find(class_="srp-controls__count-heading")
    if heading:
        bold = heading.find(class_="BOLD")
        if bold:
            return _parse_int(bold.get_text())
        return _parse_int(heading.get_text())

    # Strategy 2: results count in aria labels
    for elem in soup.find_all(attrs={"aria-label": True}):
        label = elem["aria-label"]
        if "result" in label.lower():
            return _parse_int(label)

    # Strategy 3: any element with "X results" text pattern
    text = soup.get_text()
    match = re.search(r"([\d,]+)\s+results?", text, re.I)
    if match:
        return _parse_int(match.group(1))

    logger.debug("_parse_listing_count: no count found in page")
    return 0


def _parse_avg_sold_price(html: str) -> float:
    """
    Extract listing prices from a sold results page, return average.

    Scrapes first page (~60 items) as a price sample.
    Skips price ranges (e.g. '$20.00 to $40.00') and free items.

    Returns 0.0 if no valid prices are found.
    """
    soup = BeautifulSoup(html, "lxml")
    prices: list[float] = []

    # eBay uses "s-item__price" (older) or "s-card__price" (newer)
    price_elems = soup.find_all(class_="s-item__price")
    if not price_elems:
        price_elems = soup.find_all(class_="s-card__price")
    for elem in price_elems:
        raw = elem.get_text(strip=True)
        # Skip price ranges — can't determine a single value
        if "to" in raw.lower():
            continue
        price = _parse_price(raw)
        if price and price >= 1.0:  # exclude $0 / free items
            prices.append(price)

    if not prices:
        logger.debug("_parse_avg_sold_price: no prices found")
        return 0.0

    avg = sum(prices) / len(prices)
    logger.debug(
        "_parse_avg_sold_price: %d prices, avg=$%.2f",
        len(prices),
        avg
    )
    return round(avg, 2)


def _parse_int(text: str) -> int:
    """
    Extract the first integer from a string, ignoring commas.
    Returns 0 on failure.
    """
    import re
    match = re.search(r"[\d,]+", str(text))
    if match:
        try:
            return int(match.group().replace(",", ""))
        except ValueError:
            pass
    return 0


def _parse_price(text: str) -> Optional[float]:
    """Parse a price string like '$74.00' or 'US $74.00' into float."""
    import re
    match = re.search(r"\$?([\d,]+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None

#=======================================================================
# BRAND FETCHER
#=======================================================================

async def _fetch_brand(
    session,
    brand: str,
    category: str,
    base_url: str,
    semaphore: asyncio.Semaphore,
    dry_run: bool = False,
) -> BrandResult:
    """
    Fetch sold + active data for a single brand, gated by semaphore.

    The semaphore ensures at most SEMAPHORE_LIMIT brands run
    concurrently. Jitter sleep runs AFTER the semaphore is released
    so other brands can start while we wait — maximising throughput.
    """
    result = BrandResult(brand=brand, category=category)

    async with semaphore:
        logger.info("→ Fetching brand: %s", brand)

        sold_url = _build_sold_url(brand, base_url)
        active_url = _build_active_url(brand, base_url)

        if dry_run:
            logger.info("  [dry-run] sold URL:   %s", sold_url)
            logger.info("  [dry-run] active URL: %s", active_url)
            return result

        try:
            # Fetch sold page first, then active page.
            # Playwright uses a single browser tab, so requests
            # must be sequential (each navigates the same page).
            sold_html = await fetch(session, sold_url)
            active_html = await fetch(session, active_url)
        except SoftBanError as exc:
            logger.error(
                "Soft-ban on brand '%s': %s — skipping", brand, exc
            )
            result.scrape_error = str(exc)
            return result
        except Exception as exc:
            logger.error(
                "Failed to fetch brand '%s': %s — skipping", brand, exc
            )
            result.scrape_error = str(exc)
            return result

        result.sold_90_days_count = _parse_listing_count(sold_html)
        result.active_listings_count = _parse_listing_count(active_html)
        result.avg_sold_price = _parse_avg_sold_price(sold_html)

        logger.info(
            "  %-30s sold=%-5d active=%-5d avg_price=$%.2f",
            brand,
            result.sold_90_days_count,
            result.active_listings_count,
            result.avg_sold_price,
        )

    # Jitter outside the semaphore — doesn't block the next brand
    jitter = random_jitter()
    logger.debug("Jitter sleep: %.2fs before next brand", jitter)
    await asyncio.sleep(jitter)

    return result

#=======================================================================
# ENTRY POINT
#=======================================================================

async def calculate_bolos(
    session,
    brands: list[str],
    category: str,
    base_url: str = BASE_CATEGORY_URL,
    dry_run: bool = False,
) -> list[BrandResult]:
    """
    Run Stage 2: fetch sold + active data for all brands concurrently.

    Args:
        session:   BrowserSession from http_client.build_session().
        brands:    Brand list from Stage 1.
        category:  Category label (e.g. 'casual-button-down-shirts').
        base_url:  Base eBay search URL (defaults to BASE_CATEGORY_URL).
        dry_run:   If True, logs URLs but makes no HTTP requests.

    Returns:
        List of BrandResult objects (one per brand), incl. failures.
        Failures have scrape_error set; successes have counts + price.
    """
    if not brands:
        logger.warning("Stage 2: no brands to process — skipping")
        return []

    logger.info(
        "Stage 2 — BOLO Calculator starting (%d brands, semaphore=%d)",
        len(brands),
        SEMAPHORE_LIMIT,
    )

    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    tasks = [
        _fetch_brand(
            session, brand, category, base_url, semaphore, dry_run
        )
        for brand in brands
    ]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    successful = [r for r in results if not r.scrape_error]
    failed = [r for r in results if r.scrape_error]

    logger.info(
        "Stage 2 complete — %d successful, %d failed",
        len(successful),
        len(failed),
    )

    return list(results)
