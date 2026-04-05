"""
Central configuration for the Menswear BOLO Pipeline.

All tunable parameters live here — no magic numbers scattered across spiders.
Adjust SEMAPHORE_LIMIT and JITTER_* to tune the request rate vs. scrape time tradeoff.
"""

# ── eBay URLs ─────────────────────────────────────────────────────────────────

# Stage 1 entry point: mens clothing category, Pre-owned, Buy It Now, $30+ minimum.
# _nkw=mens+-lot  → keyword "mens" excluding "lot" listings
# LH_ItemCondition=3000  → Pre-owned
# LH_BIN=1              → Buy It Now only
# _udlo=30              → minimum price $30
# _sop=16               → sort: newly listed
BASE_CATEGORY_URL = (
    "https://www.ebay.com/sch/57990/i.html"
    "?_fsrp=1&_from=R40&_nkw=mens+-lot"
    "&LH_BIN=1&_sacat=57990&LH_ItemCondition=3000&_udlo=30&_sop=16"
)

# ── Concurrency & Rate Limiting ───────────────────────────────────────────────

# Max number of brands fetched concurrently in Stage 2.
# At 2 requests/brand (sold + active), SEMAPHORE_LIMIT=3 → max 6 open connections.
# Scale up to 5 only after confirming no 429s over several weeks.
SEMAPHORE_LIMIT = 3

# Seconds to sleep after each brand's requests complete, before the next brand starts.
# Randomised so requests don't fall into a detectable fixed rhythm.
JITTER_MIN = 2.0
JITTER_MAX = 5.0

# ── Retry / Backoff (tenacity) ────────────────────────────────────────────────

MAX_RETRIES = 4         # total attempts before giving up on a URL
BACKOFF_MIN = 4.0       # seconds — minimum wait before a retry
BACKOFF_MAX = 30.0      # seconds — maximum wait before a retry (exponential cap)

# ── BOLO Thresholds ───────────────────────────────────────────────────────────

DEFAULT_COGS = 7.00         # thrift store sourcing default ($)
DEFAULT_SHIPPING_CHARGED = 8.99     # USPS Ground Advantage, mid-weight clothing ($)
SHIPPING_COST = 8.99        # avg. cost of shipping label
EBAY_FEE_RATE = 0.1161      # 12.9% FVF minus 10% Top Rated discount
EBAY_PER_ORDER_FEE = 0.30   # flat per-order fee
MIN_STR_PCT = 100.0         # minimum sell-through rate to qualify as BOLO (%)
MIN_NET_PROFIT = 20.00      # minimum net profit to qualify as BOLO ($)

# ── Output ────────────────────────────────────────────────────────────────────

OUTPUT_DIR = "data/processed"

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR = "logs"
LOG_FILENAME = "pipeline.log"
LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file before rotating
LOG_BACKUP_COUNT = 7               # keep 7 rotated files (~5–7 weeks of weekly runs)

# ── HTTP — User-Agent Pool ────────────────────────────────────────────────────

# Rotate through realistic UA strings to avoid a static fingerprint.
# All represent common desktop browser versions as of 2024.
USER_AGENTS = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Chrome / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ── HTTP — Base Headers ───────────────────────────────────────────────────────

# Headers every real browser sends. Missing these is one of the clearest bot signals.
# User-Agent is injected separately (rotated per request) — not set here.
BASE_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}
