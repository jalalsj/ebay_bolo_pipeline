"""
Menswear BOLO Pipeline — CLI entrypoint

Orchestrates Stage 1 (Brand Scout) → Stage 2 (BOLO Calculator)
→ Output (CSV).

Usage:
    python scripts/main.py --category "casual-button-down-shirts"
    python scripts/main.py --category "jeans" --cogs 15
    python scripts/main.py --category "coats" --cogs 12 --dry-run
    python scripts/main.py --category "t-shirts" --dump-html --verbose
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure scripts/ is on the path when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from calculator import (
    ebay_fees, is_bolo, net_profit, price_bucket, sell_through_rate
)
from config import (
    BASE_CATEGORY_URL, DEFAULT_COGS, DEFAULT_SHIPPING_CHARGED
)
from http_client import build_session, warm_up
from output import build_output_row, write_results, write_validation_csv
from brand_cache import load_brand_list, needs_refresh, save_brand_list
from spider_1_brand_scout import scout_brands
from spider_2_bolo_calc import (
    calculate_bolos, _build_active_url, _build_sold_url, _extract_sacat
)
from utils import setup_logging

logger = logging.getLogger(__name__)

#=======================================================================
# CLI
#=======================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bolo_pipeline",
        description=(
            "Menswear BOLO Pipeline — "
            "identify high-margin eBay resale opportunities"
        ),
    )

    parser.add_argument(
        "--category",
        type=str,
        default="menswear",
        help=(
            "Human-readable category label for the output CSV "
            "(e.g. 'casual-button-down-shirts'). "
            "Does not change the search URL."
        ),
    )
    parser.add_argument(
        "--url",
        type=str,
        default=BASE_CATEGORY_URL,
        help="Override the eBay search URL (default: config.py).",
    )
    parser.add_argument(
        "--cogs",
        type=float,
        default=None,
        help=(
            f"Cost of goods sold per item in $ "
            f"(default: ${DEFAULT_COGS:.2f} — thrift store)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Scrape and calculate but do not write output CSV. "
            "Logs results instead."
        ),
    )
    parser.add_argument(
        "--dump-html",
        action="store_true",
        help=(
            "Save raw Stage 1 HTML to data/raw/stage1_dump.html "
            "for selector debugging."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Cap the number of brands processed after Stage 1 "
            "(e.g. --limit 20 for a quick test run)."
        ),
    )
    parser.add_argument(
        "--brands",
        type=str,
        default=None,
        help=(
            "Comma-separated list of brand names to scrape directly, "
            "bypassing Stage 1 entirely "
            "(e.g. --brands 'Barbour,Canali,DOCKERS,Express,Faherty')."
        ),
    )
    parser.add_argument(
        "--validation",
        action="store_true",
        help=(
            "Write a validation CSV to data/validation/ instead of "
            "(in addition to) the standard output. "
            "Includes blank manual-research columns and eBay URLs."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (raw URLs, parse steps, jitter).",
    )

    return parser.parse_args()

#=======================================================================
# PIPELINE
#=======================================================================

async def run_pipeline(args: argparse.Namespace) -> None:
    setup_logging(verbose=args.verbose)

    # Resolve COGS — prompt interactively if not provided via flag
    cogs = args.cogs
    if cogs is None:
        try:
            raw = input(
                f"Enter your average cost of goods (COGS) per item "
                f"[default: ${DEFAULT_COGS:.2f}]: "
            ).strip()
            cogs = float(raw) if raw else DEFAULT_COGS
        except (ValueError, EOFError):
            logger.warning(
                "Invalid COGS input — using default $%.2f", DEFAULT_COGS
            )
            cogs = DEFAULT_COGS

    logger.info("═" * 60)
    logger.info("Menswear BOLO Pipeline starting")
    logger.info("  Category          : %s", args.category)
    logger.info("  COGS              : $%.2f", cogs)
    logger.info("  Shipping charged  : $%.2f", DEFAULT_SHIPPING_CHARGED)
    logger.info("  Dry run           : %s", args.dry_run)
    logger.info("═" * 60)

    async with build_session() as session:

        # Warm-up: visit homepage to collect cookies
        await warm_up(session)

        # Stage 1: Brand Scout (with cache)
        # Skip entirely when --brands is supplied — use those names directly.
        if args.brands:
            brands = [b.strip() for b in args.brands.split(",") if b.strip()]
            logger.info(
                "Brand list supplied via --brands (%d): %s",
                len(brands), brands,
            )
        else:
            # The full brand list changes slowly — re-scraping eBay on every
            # run is wasteful. Load from cache if it's still fresh; otherwise
            # run Stage 1 and save the updated list with a changelog.
            cache_key = _extract_sacat(args.url)
            brand_cache = load_brand_list(cache_key=cache_key)

            if brand_cache and not needs_refresh(brand_cache):
                brands = brand_cache["brands"]
            else:
                brands = await scout_brands(
                    session,
                    category_url=args.url,
                    dump_html=args.dump_html,
                )
                if brands:
                    old_brands = brand_cache["brands"] if brand_cache else None
                    save_brand_list(
                        brands, cache_key=cache_key, old_brands=old_brands
                    )

        if not brands:
            logger.error(
                "Pipeline aborted: no brands returned from Stage 1."
            )
            return

        if args.limit is not None:
            brands = brands[: args.limit]
            logger.info(
                "Brand list capped at %d (--limit)", args.limit
            )

        # Stage 2: BOLO Calculator
        brand_results = await calculate_bolos(
            session,
            brands=brands,
            category=args.category,
            base_url=args.url,
            dry_run=args.dry_run,
        )

    # Calculate + Filter
    output_rows = []

    for result in brand_results:
        if result.scrape_error:
            continue  # already logged in Stage 2
        if result.avg_sold_price <= 0:
            logger.debug(
                "Skipping %s — no valid average price", result.brand
            )
            continue

        str_pct = sell_through_rate(
            result.sold_90_days_count, result.active_listings_count
        )
        total_transaction = (
            result.avg_sold_price + DEFAULT_SHIPPING_CHARGED
        )
        fees = ebay_fees(total_transaction)
        profit = net_profit(result.avg_sold_price)
        bolo_flag = is_bolo(str_pct, profit)
        bucket = price_bucket(result.avg_sold_price)

        row = build_output_row(
            brand_result=result,
            str_pct=str_pct,
            fees=fees,
            net_profit=profit,
            is_bolo_flag=bolo_flag,
            bucket=bucket,
        )
        output_rows.append(row)

        status = "✓ BOLO" if bolo_flag else "✗"
        logger.info(
            "  %-30s STR=%6.1f%%  profit=$%6.2f  %s",
            result.brand,
            str_pct,
            profit,
            status,
        )

    # Write Output
    bolos = [r for r in output_rows if r["is_bolo"]]
    logger.info("─" * 60)
    logger.info(
        "Results: %d brands processed | %d BOLOs identified",
        len(output_rows),
        len(bolos),
    )

    write_results(output_rows, dry_run=args.dry_run, category=args.category)

    if args.validation and not args.dry_run:
        active_urls = {
            b: _build_active_url(b, args.url) for b in brands
        }
        sold_urls = {
            b: _build_sold_url(b, args.url) for b in brands
        }
        write_validation_csv(
            output_rows, active_urls, sold_urls, category=args.category
        )

    logger.info("Pipeline complete.")

#=======================================================================
# ENTRY POINT
#=======================================================================

def main() -> None:
    args = parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
