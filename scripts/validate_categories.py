"""
Cross-Category Validation Orchestrator

Runs main.py for each configured eBay menswear subcategory, one at a
time, with a configurable inter-run delay to avoid IP rate-limiting.

Each run produces:
  data/validation/validation_YYYY-MM-DD_{slug}.csv   ← fill in manually
  data/processed/bolo_YYYY-MM-DD_{slug}.csv           ← pipeline output

Usage examples
--------------
# Quick smoke test: 5 curated brands × 6 categories, ~10 min
python scripts/validate_categories.py --cogs 7.0 --use-samples

# Medium test: Stage 1 brand discovery, 20 brands per category, ~25 min
python scripts/validate_categories.py --cogs 7.0 --limit 20

# Single category only
python scripts/validate_categories.py --cogs 7.0 --use-samples --categories coats-jackets

# Two specific categories
python scripts/validate_categories.py --cogs 7.0 --use-samples --categories jeans,sweaters

# Dry-run (logs URLs, no HTTP requests, no files written)
python scripts/validate_categories.py --cogs 7.0 --use-samples --dry-run
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import CATEGORY_CONFIGS
from utils import setup_logging

logger = logging.getLogger(__name__)

#=======================================================================
# BRAND SAMPLES
#=======================================================================

# 5 well-known, broadly-listed brands per category.
# Used when --use-samples is passed to bypass Stage 1 (faster runs).
# One brand per letter B–F to match the validation baseline format.
CATEGORY_BRAND_SAMPLES: dict[str, list[str]] = {
    "casual-shirts": ["Barbour",          "Canali",                 "DOCKERS",  "Express",  "Faherty"],
    "coats-jackets": ["Barbour",          "Canada Goose",           "DOCKERS",  "Eddie Bauer", "Filson"],
    "jeans":         ["Bonobos",          "Citizens of Humanity",   "DKNY",     "Edwin",    "Faherty"],
    "sweaters":      ["Brooks Brothers",  "Club Monaco",            "DKNY",     "Express",  "Faherty"],
    "dress-shirts":  ["Brooks Brothers",  "Canali",                 "DKNY",     "Eton",     "Faherty"],
    "t-shirts":      ["Bape",             "Champion",               "DKNY",     "Express",  "Fruit of the Loom"],
    "pants":              ["Bonobos",       "Faherty",          "J.Crew",        "Suitsupply",      "Todd Snyder"],
    "polos":              ["Brooks Brothers", "Lacoste",        "Polo Ralph Lauren", "Fred Perry",  "Tommy Hilfiger"],
    "activewear-tops":    ["Adidas",        "Lululemon",        "Nike",          "Patagonia",       "Under Armour"],
    "hoodies-sweatshirts":["Adidas",        "Champion",         "Nike",          "Stussy",          "Supreme"],
    "activewear-pants":   ["Adidas",        "Lululemon",        "Nike",          "Patagonia",       "Under Armour"],
    "activewear-shorts":  ["Adidas",        "Lululemon",        "Nike",          "Patagonia",       "Under Armour"],
    "tracksuits":         ["Adidas",        "Fila",             "Kappa",         "Nike",            "Sergio Tacchini"],
    "activewear-jackets": ["Adidas",        "Arc'teryx",        "Nike",          "Patagonia",       "The North Face"],
    "shorts":             ["Bonobos",       "Faherty",          "J.Crew",        "Patagonia",       "Polo Ralph Lauren"],
    "swimwear":           ["Faherty",       "Orlebar Brown",    "Patagonia",     "Polo Ralph Lauren", "Vilebrequin"],
}

#=======================================================================
# CLI
#=======================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate_categories",
        description=(
            "Run the BOLO pipeline across all menswear subcategories "
            "sequentially and produce one validation CSV per category."
        ),
    )
    parser.add_argument(
        "--cogs",
        type=float,
        required=True,
        help="Cost of goods sold per item in $ (e.g. 7.0).",
    )
    parser.add_argument(
        "--use-samples",
        action="store_true",
        help=(
            "Use built-in brand samples (5 per category) instead of "
            "running Stage 1 brand discovery. Fastest option (~10 min)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Cap Stage 1 brand discovery at N brands per category. "
            "Ignored when --use-samples is set."
        ),
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help=(
            "Comma-separated list of category slugs to run "
            "(e.g. coats-jackets,jeans). Defaults to all categories."
        ),
    )
    parser.add_argument(
        "--inter-run-delay",
        type=int,
        default=90,
        help=(
            "Seconds to sleep between category runs (default: 90). "
            "Prevents eBay from rate-limiting consecutive sessions."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to each main.py invocation (no files written).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Pass --verbose to each main.py invocation.",
    )
    return parser.parse_args()

#=======================================================================
# ORCHESTRATOR
#=======================================================================

def main() -> None:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    # Resolve which categories to run
    configs = CATEGORY_CONFIGS
    if args.categories:
        requested = {s.strip() for s in args.categories.split(",")}
        configs = [c for c in CATEGORY_CONFIGS if c["slug"] in requested]
        missing = requested - {c["slug"] for c in configs}
        if missing:
            logger.warning(
                "Unknown category slugs (skipped): %s", sorted(missing)
            )

    if not configs:
        logger.error("No matching categories to run — exiting.")
        sys.exit(1)

    logger.info("═" * 60)
    logger.info("Cross-Category Validation")
    logger.info("  Categories  : %d", len(configs))
    logger.info("  COGS        : $%.2f", args.cogs)
    logger.info("  Mode        : %s", "samples" if args.use_samples else f"Stage 1 (limit={args.limit})")
    logger.info("  Dry run     : %s", args.dry_run)
    logger.info("  Inter-delay : %ds", args.inter_run_delay)
    logger.info("═" * 60)

    main_script = str(Path(__file__).parent / "main.py")
    today = date.today().strftime("%Y-%m-%d")
    output_files: list[str] = []
    failed: list[str] = []

    for i, cat in enumerate(configs):
        if i > 0:
            logger.info(
                "Sleeping %ds before next category…", args.inter_run_delay
            )
            time.sleep(args.inter_run_delay)

        logger.info("─" * 60)
        logger.info(
            "Category %d/%d: %s (%s)",
            i + 1, len(configs), cat["description"], cat["slug"],
        )

        cmd = [
            sys.executable, main_script,
            "--url",      cat["url"],
            "--category", cat["slug"],
            "--cogs",     str(args.cogs),
            "--validation",
        ]

        if args.use_samples:
            samples = CATEGORY_BRAND_SAMPLES.get(cat["slug"])
            if samples:
                cmd += ["--brands", ",".join(samples)]
            else:
                logger.warning(
                    "No sample brands defined for '%s' — running Stage 1",
                    cat["slug"],
                )
        elif args.limit is not None:
            cmd += ["--limit", str(args.limit)]

        if args.dry_run:
            cmd.append("--dry-run")
        if args.verbose:
            cmd.append("--verbose")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.error(
                "Category '%s' failed (exit %d) — continuing",
                cat["slug"], result.returncode,
            )
            failed.append(cat["slug"])
        else:
            val_path = (
                f"data/validation/validation_{today}_{cat['slug']}.csv"
            )
            output_files.append(val_path)

    # Summary
    logger.info("═" * 60)
    logger.info("Validation complete.")
    if output_files:
        logger.info("Validation CSVs written:")
        for f in output_files:
            logger.info("  %s", f)
    if failed:
        logger.warning("Failed categories: %s", failed)
    logger.info("═" * 60)


if __name__ == "__main__":
    main()
