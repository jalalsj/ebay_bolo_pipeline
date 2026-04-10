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
    "avg_sold_price",
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
        "avg_sold_price": round(brand_result.avg_sold_price, 2),
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
    rows: list[dict[str, Any]], dry_run: bool = False
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
    output_path = _build_output_path()

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

def _build_output_path() -> str:
    today = date.today().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"bolo_{today}.csv")