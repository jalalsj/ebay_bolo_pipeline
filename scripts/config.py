"""
Central configuration for the Menswear BOLO Pipeline.

All tunable parameters live here — no magic numbers scattered
across spiders. Adjust SEMAPHORE_LIMIT and JITTER_* to tune
the request rate vs. scrape time tradeoff.
"""

#=======================================================================
# EBAY URLS
#=======================================================================

# Stage 1 entry point: mens clothing, Pre-owned, Buy It Now, $30+
# _nkw=mens+-lot       → keyword "mens" excluding "lot" listings
# LH_ItemCondition=3000 → Pre-owned
# LH_BIN=1             → Buy It Now only
# _udlo=30             → minimum price $30
# _sop=16              → sort: newly listed
BASE_CATEGORY_URL = (
    "https://www.ebay.com/sch/57990/i.html"
    "?_fsrp=1&_from=R40&_nkw=mens+-lot"
    "&LH_BIN=1&_sacat=57990&LH_ItemCondition=3000&_udlo=30&_sop=16"
)

#=======================================================================
# CONCURRENCY & RATE LIMITING
#=======================================================================

# Max brands fetched concurrently in Stage 2.
# At 2 requests/brand, SEMAPHORE_LIMIT=3 → max 6 open connections.
# Scale up to 5 only after confirming no 429s over several weeks.
SEMAPHORE_LIMIT = 3

# Sleep seconds after each brand completes, before the next starts.
# Randomised so requests don't fall into a detectable fixed rhythm.
JITTER_MIN = 2.0
JITTER_MAX = 5.0

#=======================================================================
# RETRY / BACKOFF
#=======================================================================

MAX_RETRIES = 4    # total attempts before giving up on a URL
BACKOFF_MIN = 4.0  # seconds — minimum wait before a retry
BACKOFF_MAX = 30.0 # seconds — maximum wait (exponential cap)

#=======================================================================
# BOLO THRESHOLDS
#=======================================================================

DEFAULT_COGS = 7.00    # thrift store sourcing default ($)

# Shipping charged to buyer and label cost are assumed equal.
# In practice sellers often make a small margin on shipping,
# but the difference is trivial for market analysis.
DEFAULT_SHIPPING_CHARGED = 8.99  # USPS Ground Advantage ($)
SHIPPING_COST = 8.99             # avg. shipping label cost ($)

# eBay fee structure: Basic store, Top Rated Seller,
# Clothing/Shoes/Accessories category, domestic sales only.
# FVF: 12.9% minus 10% Top Rated discount = 11.61%
EBAY_FEE_RATE = 0.1161
EBAY_PER_ORDER_FEE = 0.30  # flat per-order fee ($)

MIN_STR_PCT = 100.0   # minimum STR to qualify as BOLO (%)
MIN_NET_PROFIT = 20.00 # minimum net profit to qualify ($)

#=======================================================================
# OUTPUT
#=======================================================================

OUTPUT_DIR = "data/processed"

#=======================================================================
# LOGGING
#=======================================================================

LOG_DIR = "logs"
LOG_FILENAME = "pipeline.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file before rotating
LOG_BACKUP_COUNT = 7             # keep 7 files (~5–7 weeks of runs)

#=======================================================================
# HTTP — USER-AGENT POOL
#=======================================================================

# Rotate through realistic UA strings to avoid a static fingerprint.
# All represent common desktop browser versions as of 2024.
USER_AGENTS = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
    "AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Chrome / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

#=======================================================================
# HTTP — BASE HEADERS
#=======================================================================

# Headers every real browser sends. Missing these is one of the
# clearest bot signals. User-Agent is injected separately
# (rotated per request) — not set here.
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
