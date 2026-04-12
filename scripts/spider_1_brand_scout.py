"""
Stage 1 — Brand Scout

Clicks the "See All" button in eBay's LHN Brand facet to open the
full brand dialog, then scrapes every brand name from it.

Why the "See All" dialog instead of the LHN sidebar?
  The LHN sidebar shows only 8 brands chosen by eBay's algorithm —
  typically the highest-volume brands in the category. The "See All"
  dialog exposes the complete brand list (1,800+ entries), including
  niche and low-volume brands that can be high-demand BOLOs.

Filtering philosophy:
  No count-based threshold — a brand with 3 active listings could
  be a unicorn that sells immediately. The only entries removed are
  ones that can never be brand names: entries starting with a
  non-letter character (e.g. "!it", "&Jacket", "(+)People") and the
  "Not Specified" placeholder eBay appends at the bottom.

Output: List[str] of brand names → passed to spider_2_bolo_calc.py
"""

import logging
import re

from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from config import BASE_CATEGORY_URL, BRAND_DENYLIST
from http_client import BrowserSession, SoftBanError, fetch

logger = logging.getLogger(__name__)

#=======================================================================
# CONSTANTS
#=======================================================================

# Aria-label on the "See All" button in the Brand facet.
# Stable across eBay A/B tests — tied to the dialog interaction.
_SEE_ALL_ARIA = "see all - Brand - opens dialog"

# CSS class on each brand checkbox span inside the dialog.
_BRAND_CBX_CLASS = "x-refine__multi-select-cbx"

# eBay appends this placeholder at the bottom of the brand list.
_EBAY_UNSPECIFIED = "not specified"

#=======================================================================
# DIALOG SCRAPER
#=======================================================================

async def _open_brand_dialog(session: BrowserSession) -> str:
    """
    Click the "See All" brand button and return the dialog's HTML.

    The dialog is already in the DOM but hidden. Clicking the button
    triggers eBay's JS to populate and show it. We wait for it to
    become visible before reading.

    Returns:
        Inner HTML of the brand dialog, or '' on failure.
    """
    page = session.page

    try:
        btn = page.get_by_role(
            "button", name=_SEE_ALL_ARIA
        )
        await btn.click(timeout=10000)
        logger.debug("Clicked 'See All' brand button")
    except PlaywrightTimeoutError:
        logger.warning(
            "'See All' brand button not found — "
            "eBay layout may have changed"
        )
        return ""

    try:
        dialog = page.locator("[role=dialog]:visible")
        await dialog.wait_for(timeout=10000)
        html = await dialog.inner_html()
        logger.debug(
            "Brand dialog opened — %d bytes", len(html)
        )
        return html
    except PlaywrightTimeoutError:
        logger.warning(
            "Brand dialog did not become visible after click"
        )
        return ""

#=======================================================================
# BRAND PARSER
#=======================================================================

def parse_brands_from_dialog(html: str) -> list[str]:
    """
    Extract brand names from the "See All" brand dialog HTML.

    Each brand entry in the dialog is a checkbox span with class
    x-refine__multi-select-cbx. Its parent div contains the text:
      "BrandName(count) Items(count)"

    Only entries starting with a letter are kept — this removes
    parsing artifacts like "!it", "&Jacket", "(+)People" that are
    not real brand names. The "Not Specified" placeholder is also
    removed.

    Args:
        html: Inner HTML of the brand dialog.

    Returns:
        List of brand name strings, in order of appearance.
        Empty list if the dialog HTML is empty or unparseable.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    brands: list[str] = []

    for span in soup.find_all("span", class_=_BRAND_CBX_CLASS):
        raw = span.parent.get_text(strip=True)
        name = _clean_brand_text(raw)
        if not name:
            continue
        if name.lower() == _EBAY_UNSPECIFIED:
            continue
        # Keep only entries that start with a letter —
        # artifacts like "!it", "&Jacket" start with symbols
        if not name[0].isalpha():
            continue
        # Remove known non-brand terms (style descriptors, generic words)
        if name.lower() in BRAND_DENYLIST:
            continue
        brands.append(name)

    logger.info(
        "Dialog parser: %d brands extracted", len(brands)
    )
    return brands


def parse_brands_from_lhn(html: str) -> list[str]:
    """
    Fallback: parse the 8 visible brands from the LHN sidebar.

    Used only when the "See All" dialog is unavailable (e.g. the
    button is not found or the dialog fails to open). Returns at
    most 8 brands — far fewer than the dialog strategy.

    Args:
        html: Raw HTML of the eBay category search page.

    Returns:
        List of brand name strings from the LHN sidebar.
    """
    soup = BeautifulSoup(html, "lxml")
    brands: list[str] = []

    for title_div in soup.find_all(
        class_="x-refine__item__title-container"
    ):
        if title_div.get_text(strip=True).lower() != "brand":
            continue
        container = title_div.find_parent("li")
        if container is None:
            continue
        for link in container.find_all("a", href=True):
            name = _clean_brand_text(link.get_text())
            if name and len(name) > 1:
                brands.append(name)
        if brands:
            logger.info(
                "LHN fallback: found %d brands", len(brands)
            )
            return _deduplicate(brands)

    logger.warning(
        "LHN fallback: no brands found. "
        "Run with --dump-html to inspect the page."
    )
    return []

#=======================================================================
# HELPERS
#=======================================================================

def _clean_brand_text(raw: str) -> str:
    """
    Strip count suffixes and whitespace from a brand label.

    Examples:
        'Faherty(1,382) Items(1,382)' → 'Faherty'
        'Polo Ralph Lauren (9,674) Items' → 'Polo Ralph Lauren'
        '  L.L. Bean (3,304) Items  ' → 'L.L. Bean'
    """
    cleaned = re.split(r"\s*\(", raw)[0].strip()
    cleaned = re.sub(r"\s*Items\s*$", "", cleaned).strip()
    return cleaned


def _deduplicate(items: list[str]) -> list[str]:
    """Return items with duplicates removed, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

#=======================================================================
# ENTRY POINT
#=======================================================================

async def scout_brands(
    session: BrowserSession,
    category_url: str = BASE_CATEGORY_URL,
    dump_html: bool = False,
) -> list[str]:
    """
    Navigate to the eBay category page, open the brand dialog,
    and return the full list of brand candidates.

    Strategy:
      1. Load the category search page via fetch()
      2. Click "See All" to open the full brand dialog
      3. Parse all brand names from the dialog
      4. Fall back to the 8-brand LHN sidebar if the dialog fails

    Args:
        session:      BrowserSession from http_client.build_session().
        category_url: eBay search URL to scrape (defaults to config).
        dump_html:    If True, saves page HTML to data/raw/ for debug.

    Returns:
        List of brand name strings to pass to Stage 2.
    """
    logger.info("Stage 1 — Brand Scout starting")
    logger.info("URL: %s", category_url)

    try:
        html = await fetch(session, category_url)
    except SoftBanError as exc:
        logger.error("Stage 1 aborted: %s", exc)
        return []

    if not html:
        logger.error("Stage 1: empty response — aborting")
        return []

    if dump_html:
        _dump_raw_html(html, "data/raw/stage1_page.html")

    # Primary: full brand list from the "See All" dialog
    dialog_html = await _open_brand_dialog(session)

    if dialog_html:
        if dump_html:
            _dump_raw_html(dialog_html, "data/raw/stage1_dialog.html")
        brands = parse_brands_from_dialog(dialog_html)
    else:
        logger.warning(
            "Brand dialog unavailable — falling back to LHN sidebar"
        )
        brands = parse_brands_from_lhn(html)

    brands = _deduplicate(brands)

    if not brands:
        logger.warning(
            "Stage 1 returned 0 brands. "
            "Run with --dump-html to inspect."
        )
    else:
        logger.info(
            "Stage 1 complete — %d brands found (first 10: %s)",
            len(brands),
            brands[:10],
        )

    return brands


def _dump_raw_html(html: str, path: str) -> None:
    """Write raw HTML to disk for selector debugging."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    logger.info("HTML dumped to %s", path)
