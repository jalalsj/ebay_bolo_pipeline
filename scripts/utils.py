"""
Shared utilities for the BOLO pipeline:
  - Logging: stdout + rotating file handler (logs/pipeline.log)
  - Soft-ban detection: recognise eBay challenge / CAPTCHA pages
  - Jitter: random sleep duration within configured bounds
"""

import logging
import logging.handlers
import random
from pathlib import Path

from config import (
    JITTER_MIN,
    JITTER_MAX,
    LOG_DIR,
    LOG_FILENAME,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)

#=======================================================================
# SOFT-BAN DETECTION
#=======================================================================

# Strings eBay injects into challenge / block pages.
# Any one of these in the response body signals we should back off.
_SOFT_BAN_SIGNALS = [
    "pardon our interruption",
    "verify you are a human",
    "please complete the security check",
    "unusual activity",
    "access to this page has been denied",
    "robot or automated",
    "ebay is temporarily unavailable",
    "checking your browser before you access",
]


def is_soft_banned(html: str) -> bool:
    """
    Return True if the response looks like an eBay challenge page.

    Checks are case-insensitive substring matches. A positive result
    means the response should be discarded and the brand skipped.
    """
    lowered = html.lower()
    for signal in _SOFT_BAN_SIGNALS:
        if signal in lowered:
            logging.getLogger(__name__).warning(
                "Soft-ban signal detected: '%s'", signal
            )
            return True
    return False

#=======================================================================
# JITTER
#=======================================================================

def random_jitter() -> float:
    """
    Return a random sleep duration (seconds) in [JITTER_MIN, JITTER_MAX].

    Called after each brand's request pair completes so the inter-brand
    timing is non-deterministic — harder for eBay to fingerprint.
    """
    return random.uniform(JITTER_MIN, JITTER_MAX)

#=======================================================================
# LOGGING
#=======================================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure the root logger with two handlers:
      1. StreamHandler        → stdout (good for interactive runs)
      2. RotatingFileHandler  → logs/pipeline.log (persistent for cron)

    The rotating handler keeps LOG_BACKUP_COUNT files, each up to
    LOG_MAX_BYTES, so the log directory never grows unbounded.

    Args:
        verbose: If True, sets level to DEBUG (raw URLs, parse steps).
                 If False (default), INFO — progress and warnings only.

    Returns:
        The configured root logger. Module-level loggers created via
        logging.getLogger(__name__) will inherit this configuration.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = (
        "%(asctime)s [%(levelname)-8s] [%(name)-25s] %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    log_path = Path(LOG_DIR) / LOG_FILENAME

    root = logging.getLogger()
    root.setLevel(log_level)

    # Guard: don't add duplicate handlers on repeated calls
    if root.handlers:
        return root

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # 1. Stdout — always present
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # 2. Rotating file — persistent across cron runs
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return root
