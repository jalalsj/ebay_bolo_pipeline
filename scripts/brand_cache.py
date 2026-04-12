"""
Brand list cache — persistent storage for Stage 1 results.

Stage 1 scrapes 1,800+ brands from eBay's brand facet dialog.
That list changes slowly — new brands appear, dead ones drop off,
but the week-to-week delta is small. Re-scraping it on every run
wastes time and adds unnecessary eBay requests.

This module caches the brand list to disk (JSON) and tracks a
changelog of what was added or removed each time Stage 1 does run.

Usage in main.py:
    cache = load_brand_list()
    if cache and not needs_refresh(cache):
        brands = cache["brands"]   # use cached list, skip Stage 1
    else:
        brands = await scout_brands(...)
        save_brand_list(brands, old_brands=cache["brands"] if cache else None)

Cache file format (data/brands/brand_list.json):
    {
      "last_scraped": "2026-04-10",
      "brands": ["A. Tiziano", "A Bathing Ape", ...],
      "changelog": [
        {
          "date": "2026-04-10",
          "added": ["NewBrand"],
          "removed": ["OldBrand"]
        }
      ]
    }
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from config import BRAND_CACHE_MAX_AGE_DAYS, BRAND_CACHE_PATH

logger = logging.getLogger(__name__)

#=======================================================================
# PATH HELPER
#=======================================================================

def _cache_path(cache_key: str = "57990") -> Path:
    """
    Resolve the JSON cache file path for a given eBay sacat/cache key.

    The default key ("57990" — men's clothing) maps to the legacy
    filename brand_list.json for backward compatibility. All other
    keys use brand_list_{cache_key}.json in the same directory.
    """
    base = Path(BRAND_CACHE_PATH)
    if cache_key == "57990":
        return base
    return base.parent / f"brand_list_{cache_key}.json"


#=======================================================================
# LOAD
#=======================================================================

def load_brand_list(cache_key: str = "57990") -> Optional[dict]:
    """
    Load the cached brand list from disk.

    Returns:
        The parsed cache dict, or None if the file doesn't exist
        or is unreadable.
    """
    path = _cache_path(cache_key)
    if not path.exists():
        logger.info("Brand cache not found — Stage 1 will run")
        return None

    try:
        with open(path, "r", encoding="utf-8") as fh:
            cache = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Brand cache unreadable (%s) — Stage 1 will run", exc
        )
        return None

    brand_count = len(cache.get("brands", []))
    logger.info(
        "Brand cache loaded — %d brands, last scraped %s",
        brand_count,
        cache.get("last_scraped", "unknown"),
    )
    return cache

#=======================================================================
# STALENESS CHECK
#=======================================================================

def needs_refresh(cache: dict) -> bool:
    """
    Return True if the cached brand list should be re-scraped.

    The cache is stale when it is older than BRAND_CACHE_MAX_AGE_DAYS
    or when the last_scraped date is missing or malformed.

    Args:
        cache: Dict returned by load_brand_list().

    Returns:
        True  → run Stage 1 and refresh the cache.
        False → use cache["brands"] directly.
    """
    last_scraped_str = cache.get("last_scraped")
    if not last_scraped_str:
        logger.warning(
            "Brand cache has no last_scraped date — refreshing"
        )
        return True

    try:
        last_scraped = date.fromisoformat(last_scraped_str)
    except ValueError:
        logger.warning(
            "Brand cache last_scraped '%s' is invalid — refreshing",
            last_scraped_str,
        )
        return True

    age_days = (date.today() - last_scraped).days

    if age_days >= BRAND_CACHE_MAX_AGE_DAYS:
        logger.info(
            "Brand cache is %d days old (limit: %d) — refreshing",
            age_days,
            BRAND_CACHE_MAX_AGE_DAYS,
        )
        return True

    logger.info(
        "Brand cache is %d days old — using %d cached brands "
        "(refreshes in %d days)",
        age_days,
        len(cache.get("brands", [])),
        BRAND_CACHE_MAX_AGE_DAYS - age_days,
    )
    return False

#=======================================================================
# SAVE
#=======================================================================

def save_brand_list(
    new_brands: list[str],
    cache_key: str = "57990",
    old_brands: Optional[list[str]] = None,
) -> None:
    """
    Write the brand list to disk, appending a changelog entry.

    Computes the diff against old_brands (if provided) so the file
    records exactly what changed since the last scrape. All previous
    changelog entries are preserved.

    Args:
        new_brands: Fresh brand list from Stage 1.
        old_brands: Previous brand list (from the prior cache).
                    Pass None on the very first run.
    """
    today = date.today().isoformat()

    # Build this run's changelog entry
    changelog_entry: dict = {"date": today, "added": [], "removed": []}
    if old_brands is not None:
        old_set = set(old_brands)
        new_set = set(new_brands)
        added   = sorted(new_set - old_set)
        removed = sorted(old_set - new_set)
        changelog_entry["added"]   = added
        changelog_entry["removed"] = removed
        logger.info(
            "Brand list diff: +%d added, -%d removed",
            len(added),
            len(removed),
        )
        if added:
            logger.debug("Added brands:   %s", added[:20])
        if removed:
            logger.debug("Removed brands: %s", removed[:20])

    # Preserve existing changelog history
    path = _cache_path(cache_key)
    prior_changelog: list = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            prior_changelog = existing.get("changelog", [])
        except (json.JSONDecodeError, OSError):
            pass  # start fresh if the old file is corrupt

    cache = {
        "last_scraped": today,
        "brands": new_brands,
        "changelog": prior_changelog + [changelog_entry],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=2, ensure_ascii=False)

    logger.info(
        "Brand cache saved → %s (%d brands)", path, len(new_brands)
    )
