"""
Stage 1 — Brand Scout

Fetches the eBay category search page and extracts brand names
from the Left-Hand Navigation (LHN) sidebar refinements panel.

Why the LHN sidebar?
  eBay's LHN lists the brands most frequently appearing in the
  current filtered view (Pre-owned, Buy It Now, $30+). This gives
  us the high-activity brands worth investigating in Stage 2 —
  we don't need to guess or maintain a static watchlist.

Output: List[str] of brand names → passed to spider_2_bolo_calc.py
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from config import BASE_CATEGORY_URL
from http_client import SoftBanError, fetch
from utils import is_soft_banned

logger = logging.getLogger(__name__)

#=======================================================================
# HTML SELECTORS
#=======================================================================

# eBay's HTML structure changes with A/B tests and full redesigns.
# This module tries multiple selector strategies in order, falling
# back gracefully.
#
# To debug: run with --dump-html flag in main.py to save raw HTML
# to disk, then inspect it to find the correct selectors for the
# current eBay layout.

_BRAND_SECTION_KEYWORDS = ["brand", "brands"]

#=======================================================================
# BRAND PARSER
#=======================================================================

def parse_brands_from_lhn(html: str) -> list[str]:
    """
    Parse brand names from eBay's LHN sidebar refinements.

    Tries the following strategies in order:
      1. Find <section> or <div> with a heading containing "Brand",
         then grab sibling <a> links
      2. Look for <a> tags inside a known facet container class
      3. Fallback: regex search for brand-like anchor patterns

    Args:
        html: Raw HTML string from the eBay category search page.

    Returns:
        List of brand name strings, deduplicated and in order of
        appearance. Returns an empty list if no brands are found.
    """
    soup = BeautifulSoup(html, "lxml")
    brands: list[str] = []

    # Strategy 1: find the Brand heading by its known container class,
    # walk up to the enclosing <li>, grab all <a> links inside
    for title_div in soup.find_all(
        class_="x-refine__item__title-container"
    ):
        if title_div.get_text(strip=True).lower() != "brand":
            continue
        container = title_div.find_parent("li")
        if container is None:
            continue

        for link in container.find_all("a", href=True):
            brand_name = _clean_brand_text(link.get_text())
            if brand_name and len(brand_name) > 1:
                brands.append(brand_name)

        if brands:
            logger.info(
                "Strategy 1: found %d brands via heading search",
                len(brands)
            )
            return _deduplicate(brands)

    # Strategy 2: eBay aspect/facet container classes (2023-2024)
    facet_classes = [
        "x-refine__select__svg",  # older layout
        "brm-facet",              # newer layout
        "x-refine__main__list",   # search results page
    ]
    for css_class in facet_classes:
        for container in soup.find_all(class_=css_class):
            heading_text = container.get_text(separator=" ").lower()
            if not any(
                kw in heading_text for kw in _BRAND_SECTION_KEYWORDS
            ):
                continue
            for link in container.find_all("a", href=True):
                brand_name = _clean_brand_text(link.get_text())
                if brand_name and len(brand_name) > 1:
                    brands.append(brand_name)
            if brands:
                logger.info(
                    "Strategy 2 (class=%s): found %d brands",
                    css_class,
                    len(brands)
                )
                return _deduplicate(brands)

    # Strategy 3: regex fallback — eBay brand links contain "Brand="
    for link in soup.find_all("a", href=re.compile(r"Brand=", re.I)):
        brand_name = _clean_brand_text(link.get_text())
        if brand_name and len(brand_name) > 1:
            brands.append(brand_name)

    if brands:
        logger.info(
            "Strategy 3 (regex fallback): found %d brands", len(brands)
        )
        return _deduplicate(brands)

    logger.warning(
        "No brands found in LHN sidebar. The eBay HTML structure "
        "may have changed. Re-run with --dump-html to inspect."
    )
    return []

#=======================================================================
# HELPERS
#=======================================================================

def _clean_brand_text(raw: str) -> str:
    """
    Strip count suffixes and noise from a brand label.

    Examples:
      '  Faherty (91)\\n'               → 'Faherty'
      'Polo Ralph Lauren (9,674) Items' → 'Polo Ralph Lauren'
    """
    # Remove everything from the first '(' onwards
    cleaned = re.split(r"\s*\(", raw)[0].strip()
    # Also strip trailing "Items" in case it appears without parens
    cleaned = re.sub(r"\s*Items\s*$", "", cleaned).strip()
    return cleaned


def _deduplicate(items: list[str]) -> list[str]:
    """Return items with duplicates removed, preserving original order."""
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
    session,
    category_url: str = BASE_CATEGORY_URL,
    dump_html: bool = False,
) -> list[str]:
    """
    Fetch the eBay category page and return a list of brand candidates.

    Args:
        session:      BrowserSession from http_client.build_session().
        category_url: eBay search URL to scrape (defaults to config).
        dump_html:    If True, writes raw HTML to data/raw/ for debug.

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
        _dump_raw_html(html, "data/raw/stage1_dump.html")

    brands = parse_brands_from_lhn(html)

    if not brands:
        logger.warning(
            "Stage 1 returned 0 brands. "
            "Check selectors or run with --dump-html."
        )
    else:
        logger.info(
            "Stage 1 complete — %d brands found: %s",
            len(brands),
            brands[:10]
        )

    return brands


def _dump_raw_html(html: str, path: str) -> None:
    """Write raw HTML to disk for selector debugging."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    logger.info("Raw HTML dumped to %s", path)
