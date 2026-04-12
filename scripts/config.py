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
# Playwright uses a single browser tab, so only 1 brand can
# be in-flight at a time. Keep at 1 to avoid navigation races.
SEMAPHORE_LIMIT = 1

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
# PRICE BUCKETS
#=======================================================================

# Fashion retail tier names with their upper price bounds.
# Lower bound of each tier is implied by the tier below it.
# Outerwear uses different thresholds — deferred to v2.
BUCKET_BREAD_AND_BUTTER = ("Bread & Butter", 150.00)  # $30–150
BUCKET_HIGH_END         = ("High-End",        500.00)  # $151–500
BUCKET_LUXURY           = ("Luxury",     float("inf"))  # $501+

PRICE_BUCKETS = [
    BUCKET_BREAD_AND_BUTTER,
    BUCKET_HIGH_END,
    BUCKET_LUXURY,
]

#=======================================================================
# BRAND DENYLIST
#=======================================================================

# Generic terms that appear in eBay's brand facet but are not real brands.
# All entries are lowercase — comparison is case-insensitive.
# Add to this list as new non-brands are discovered during validation.
BRAND_DENYLIST = {
    "abstract",   # style descriptor
    "academy",    # generic retailer name
    "active",     # generic descriptor
}

#=======================================================================
# OUTPUT
#=======================================================================

OUTPUT_DIR = "data/processed"

#=======================================================================
# MENSWEAR SUBCATEGORY CONFIGS
#=======================================================================

# Each entry defines one eBay menswear subcategory to scrape.
# sacat values are eBay's internal category identifiers.
# URL mirrors BASE_CATEGORY_URL structure with the subcategory sacat.
# Verify each URL in a browser with --dry-run before a full run.
CATEGORY_CONFIGS = [
    {
        "slug": "casual-shirts",
        "sacat": "57990",
        "url": BASE_CATEGORY_URL,
        "description": "Men's Casual Button-Down Shirts",
    },
    {
        "slug": "coats-jackets",
        "sacat": "57988",
        "url": (
            "https://www.ebay.com/sch/57988/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=57988&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Coats & Jackets",
    },
    {
        "slug": "jeans",
        "sacat": "11483",
        "url": (
            "https://www.ebay.com/sch/11483/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=11483&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Jeans",
    },
    {
        "slug": "sweaters",
        "sacat": "11484",
        "url": (
            "https://www.ebay.com/sch/11484/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=11484&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Sweaters",
    },
    {
        "slug": "dress-shirts",
        "sacat": "57991",
        "url": (
            "https://www.ebay.com/sch/57991/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=57991&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Dress Shirts",
    },
    {
        "slug": "t-shirts",
        "sacat": "185100",
        "url": (
            "https://www.ebay.com/sch/185100/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=185100&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's T-Shirts",
    },
    {
        "slug": "pants",
        "sacat": "57989",
        "url": (
            "https://www.ebay.com/sch/57989/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=57989&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Pants",
    },
    {
        "slug": "polos",
        "sacat": "185101",
        "url": (
            "https://www.ebay.com/sch/185101/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=185101&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Polo Shirts",
    },
    {
        "slug": "activewear-tops",
        "sacat": "185076",
        "url": (
            "https://www.ebay.com/sch/185076/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=185076&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Activewear Tops",
    },
    {
        "slug": "hoodies-sweatshirts",
        "sacat": "155183",
        "url": (
            "https://www.ebay.com/sch/155183/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=155183&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Hoodies & Sweatshirts",
    },
    {
        "slug": "activewear-pants",
        "sacat": "260956",
        "url": (
            "https://www.ebay.com/sch/260956/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=260956&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Activewear Pants",
    },
    {
        "slug": "activewear-shorts",
        "sacat": "260957",
        "url": (
            "https://www.ebay.com/sch/260957/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=260957&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Activewear Shorts",
    },
    {
        "slug": "tracksuits",
        "sacat": "185708",
        "url": (
            "https://www.ebay.com/sch/185708/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=185708&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Tracksuits & Sets",
    },
    {
        "slug": "activewear-jackets",
        "sacat": "185702",
        "url": (
            "https://www.ebay.com/sch/185702/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=185702&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Activewear Jackets",
    },
    {
        "slug": "shorts",
        "sacat": "15689",
        "url": (
            "https://www.ebay.com/sch/15689/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=15689&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Shorts",
    },
    {
        "slug": "swimwear",
        "sacat": "15690",
        "url": (
            "https://www.ebay.com/sch/15690/i.html"
            "?_fsrp=1&_from=R40&_nkw=mens+-lot"
            "&LH_BIN=1&_sacat=15690&LH_ItemCondition=3000&_udlo=30&_sop=16"
        ),
        "description": "Men's Swimwear",
    },
]

#=======================================================================
# BRAND CACHE
#=======================================================================

# Path to the persistent brand list cache file.
BRAND_CACHE_PATH = "data/brands/brand_list.json"

# How many days before the cached brand list is considered stale
# and Stage 1 re-scrapes eBay. 30 days is a safe default —
# the brand facet doesn't change meaningfully week to week.
BRAND_CACHE_MAX_AGE_DAYS = 30

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

