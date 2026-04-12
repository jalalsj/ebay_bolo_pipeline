"""
Output writer for the BOLO pipeline.

Enforces the CSV schema and writes results to a dated file.
Output path: data/processed/bolo_YYYY-MM-DD.csv

Schema matches README exactly so downstream tools (pandas, BI)
can consume without transformation.
"""

import csv
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from config import OUTPUT_DIR, DEFAULT_COGS, SHIPPING_COST

VALIDATION_DIR = "data/validation"

logger = logging.getLogger(__name__)

#=======================================================================
# SCHEMA
#=======================================================================

# Column order matches the README output schema
FIELDNAMES = [
    "date_scraped",
    "category",
    "brand",
    "active_listings_count",
    "sold_90_days_count",
    "sell_through_rate",
    "avg_price_sold_recent",
    "avg_price_active_recent",
    "price_bucket",
    "cogs",
    "ebay_fees",
    "shipping_cost",
    "estimated_net_profit",
    "is_bolo",
]

#=======================================================================
# ROW BUILDER
#=======================================================================

def build_output_row(
    brand_result,      # BrandResult from spider_2_bolo_calc
    str_pct: float,
    fees: float,
    net_profit: float,
    is_bolo_flag: bool,
    bucket: str,
) -> dict[str, Any]:
    """
    Map a BrandResult + calculated values into a flat output row.

    Keeps all formatting (rounding) consistent in one place.
    COGS and shipping values are pulled from config defaults.
    """
    return {
        "date_scraped": date.today().isoformat(),
        "category": brand_result.category,
        "brand": brand_result.brand,
        "active_listings_count": brand_result.active_listings_count,
        "sold_90_days_count": brand_result.sold_90_days_count,
        "sell_through_rate": round(str_pct, 2),
        "avg_price_sold_recent": round(brand_result.avg_sold_price, 2),
        "avg_price_active_recent": round(brand_result.avg_active_price, 2),
        "price_bucket": bucket,
        "cogs": round(DEFAULT_COGS, 2),
        "ebay_fees": round(fees, 2),
        "shipping_cost": round(SHIPPING_COST, 2),
        "estimated_net_profit": round(net_profit, 2),
        "is_bolo": int(is_bolo_flag),  # 1 / 0 for easy CSV filtering
    }

#=======================================================================
# CSV WRITER
#=======================================================================

def write_results(
    rows: list[dict[str, Any]], dry_run: bool = False, category: str = ""
) -> str:
    """
    Write BOLO results to a dated CSV file.

    Args:
        rows:    List of result dicts — must contain all FIELDNAMES.
        dry_run: If True, skips file write and logs instead.

    Returns:
        Absolute path to the written CSV, '[dry-run]' if dry_run
        is True, or '' if rows is empty.
    """
    output_path = _build_output_path(category)

    if dry_run:
        logger.info(
            "[dry-run] Would write %d rows to %s",
            len(rows), output_path
        )
        for row in rows:
            logger.debug("[dry-run] row: %s", row)
        return "[dry-run]"

    if not rows:
        logger.warning("No rows to write — output file not created")
        return ""

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=FIELDNAMES, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d rows → %s", len(rows), output_path)
    return output_path

#=======================================================================
# HELPERS
#=======================================================================

def _build_output_path(category: str = "") -> str:
    today = date.today().strftime("%Y-%m-%d")
    suffix = f"_{category}" if category else ""
    return os.path.join(OUTPUT_DIR, f"bolo_{today}{suffix}.csv")


#=======================================================================
# VALIDATION CSV
#=======================================================================

# Header matches the hand-built validation sheet format:
# Each "manual_*" metric has a sibling URL column for quick lookup.
_VALIDATION_HEADER = [
    "brand",
    "scraper_active_listings",
    "manual_active_listings",
    "manual_active_listings",   # URL column
    "scraper_sold_90d",
    "manual_sold_90d",
    "manual_sold_90d",          # URL column
    "scraper_avg_price_sold_recent",
    "manual_avg_price_sold_recent",
    "manual_avg_price_sold_recent_url",  # URL column (blank — calculated field)
    "scraper_str_pct",
    "manual_str_pct",
    "scraper_net_profit",
    "manual_net_profit",
    "scraper_is_bolo",
    "manual_is_bolo",
    "notes",
]


def write_validation_csv(
    rows: list[dict[str, Any]],
    active_urls: dict[str, str],
    sold_urls: dict[str, str],
    category: str = "",
) -> str:
    """
    Write a validation CSV with scraper values + blank manual columns.

    Produces data/validation/validation_YYYY-MM-DD.csv.  Each row
    contains the scraped numbers alongside empty cells and eBay search
    URLs so you can quickly verify figures by hand.

    Args:
        rows:         Output rows from build_output_row().
        active_urls:  brand → active-listings search URL.
        sold_urls:    brand → sold-listings search URL.

    Returns:
        Absolute path of the written file, or '' if rows is empty.
    """
    if not rows:
        logger.warning("No rows for validation CSV — file not created")
        return ""

    today = date.today().strftime("%Y-%m-%d")
    Path(VALIDATION_DIR).mkdir(parents=True, exist_ok=True)
    suffix = f"_{category}" if category else ""
    out_path = os.path.join(VALIDATION_DIR, f"validation_{today}{suffix}.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_VALIDATION_HEADER)
        for row in rows:
            brand = row["brand"]
            str_pct = (
                f"{row['sell_through_rate']:.1f}%"
                if isinstance(row["sell_through_rate"], (int, float))
                else row["sell_through_rate"]
            )
            writer.writerow([
                brand,
                row["active_listings_count"],   # scraper_active_listings
                "",                             # manual_active_listings
                active_urls.get(brand, ""),     # active URL
                row["sold_90_days_count"],       # scraper_sold_90d
                "",                             # manual_sold_90d
                sold_urls.get(brand, ""),        # sold URL
                row["avg_price_sold_recent"],    # scraper_avg_price_sold_recent
                "",                             # manual_avg_price_sold_recent
                "",                             # avg_sold URL (n/a)
                str_pct,                        # scraper_str_pct
                "",                             # manual_str_pct
                row["estimated_net_profit"],     # scraper_net_profit
                "",                             # manual_net_profit
                row["is_bolo"],                 # scraper_is_bolo
                "",                             # manual_is_bolo
                "",                             # notes
            ])

    logger.info("Validation CSV → %s (%d rows)", out_path, len(rows))
    return out_path