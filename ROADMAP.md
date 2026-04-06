# Menswear BOLO Pipeline — Product Roadmap

## Overview

An automated data pipeline that identifies high-margin menswear
resale opportunities on eBay. The system scrapes sell-through rates
and pricing data across brands, applies a profitability model, and
surfaces weekly sourcing intelligence for resellers.

**Stack:** Python, aiohttp, BeautifulSoup, pandas, SQLite

---

## Team

| Name         | Role                  | Responsibilities                          |
|--------------|-----------------------|-------------------------------------------|
| Jalal Janjua | Data Analyst          | Business logic, profitability model,      |
|              |                       | data analysis, pipeline requirements      |
| Claude       | Software Engineer     | Architecture, scraping infrastructure,    |
|              |                       | anti-ban measures, code review            |

---

## Milestone 1 — Profitability Calculator
**Branch:** `feature/calculator` | **Status:** ✅ Complete

Implements the core business logic for evaluating resale
opportunities. Establishes the BOLO qualification criteria:
sell-through rate ≥ 100% and net profit ≥ $20.

**Scope:**
- Sell-through rate calculation
- eBay fee model: 11.61% FVF (Top Rated Seller) + $0.30/order,
  applied to total transaction value including shipping
- Net profit formula accounting for COGS, fees, and shipping label
- BOLO qualification logic

**Definition of done:** 23 unit tests passing across all functions.

---

## Milestone 2 — eBay Scraper
**Branch:** `feature/scraper` | **Status:** 🔄 In Progress

Async scraping layer that feeds real market data into the
profitability calculator. Designed to run weekly without triggering
eBay's bot detection.

**Scope:**
- Stage 1: LHN sidebar brand extraction from eBay category pages
- Stage 2: Concurrent sold/active listing fetcher per brand
- Anti-ban layer: UA rotation, exponential backoff, soft-ban
  detection
- Configurable concurrency (semaphore) and jitter rate limiting

**Definition of done:** Successful live scrape run returning valid
brand data across all qualifying categories.

---

## Milestone 3 — Pipeline Orchestration
**Branch:** `feature/pipeline` | **Status:** ⏳ Planned

Wires Stage 1 → Stage 2 → Calculator → Output into a single
runnable CLI command. Produces dated CSV output ready for analysis.

**Scope:**
- CLI entrypoint with `--dry-run`, `--dump-html`, `--verbose` flags
- End-to-end orchestration with structured logging
- CSV output with enforced schema for downstream consumption

**Definition of done:** Full pipeline run from CLI produces a valid,
correctly formatted CSV with BOLO-qualified brands.

---

## Milestone 4 — Analysis Layer
**Branch:** `feature/analysis` | **Status:** ⏳ Planned

Transforms raw pipeline output into actionable sourcing intelligence.
Introduces SQLite persistence for historical trend tracking.

**Scope:**
- pandas-based analysis: filtering, ranking, summary statistics
- SQLite persistence layer replacing CSV output
- Historical trend queries: STR and profit per brand over time
- Weekly BOLO report generation

**Definition of done:** Trend analysis operational across a minimum
of 4 weeks of pipeline data.

---

## Milestone 5 — Visualisation
**Branch:** `feature/viz` | **Status:** ⏳ Planned

Communicates sourcing intelligence through charts and dashboards,
enabling faster decision-making for resellers.

**Scope:**
- STR and profit trend charts per brand
- Weekly BOLO summary dashboard
- Category-level performance comparison

**Definition of done:** Dashboard renders correctly on live pipeline
data and is shareable with end users.

---

## Branch Strategy

```
main
  ├── feature/calculator  ✅ merge after unit tests pass
  ├── feature/scraper     merge after successful live scrape
  ├── feature/pipeline    merge after end-to-end validation
  ├── feature/analysis    merge after 4 weeks of trend data
  └── feature/viz         merge after dashboard validated on live
                          data
```

All features are developed on isolated branches and merged to `main`
via pull request. No feature is merged with failing tests.

---

## V2 Considerations

- Scraper unit tests using saved HTML fixtures
- Scheduled execution via cron or Airflow
- Newsletter delivery via Resend API
- PostgreSQL for multi-user or hosted deployment
