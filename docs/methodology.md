# Pipeline Methodology

## Price Sampling — V1

### `avg_price_sold_recent`
Average of prices from the **first page (~60 listings)** of sold results,
sorted by **ended recently** (`_sop=10`). Reflects the most recently
completed sales for the brand in the given category. No price floor applied.

### `avg_price_active_recent`
Average of prices from the **first page (~60 listings)** of active BIN
listings, sorted by **newly listed** (`_sop=10`). Reflects the most recently
listed prices. No price floor applied.

### Sell-Through Rate (STR)
```
STR = sold_90_days_count / active_listings_count
```
Both counts use **no price floor** (`_udlo` removed) to avoid population
bias — filtering active and sold by the same price minimum does not produce
a true ratio because the price distributions of the two populations differ.

### What is not included in V1
- Sub-$1 items are excluded from price averaging (likely data errors).
- Price ranges (e.g. "$20.00 to $40.00") are excluded — no single value to
  extract.
- Only page 1 of results is sampled for average price. For high-volume
  brands this is a recency-biased sample, not a population average.

---

## V2 Intent

Replace page-1 HTML sampling with a full per-listing dataset:

- **Data source:** eBay Finding API (`findCompletedItems`) + Browse API for
  active listings. Returns structured JSON per listing — no HTML parsing.
- **Storage:** SQLite database, one row per listing.
  Schema: `brand, category, title, price, condition, sold_date,
  listing_type (active/sold), scraped_at`
- **Aggregation:** Computed in Python/pandas at query time — averages,
  percentiles, STR, and any user-defined price window.
- **Online tool:** SQLite + FastAPI/Flask enables resellers to set their own
  filters (price range, category, STR threshold, date window) without
  re-scraping.
- **Coverage:** eBay API returns up to 10,000 results per search vs. ~1,000
  via the search UI. Rate limit: 5,000 calls/day on the basic tier.
