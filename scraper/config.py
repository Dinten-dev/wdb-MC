"""Zentrale Konfiguration für den ImmoScout24-Scraper.

Enthält alle Konstanten, CSS-Selektoren, Chrome-Optionen,
Timing-Parameter und Output-Pfade. Keine Werte werden im
restlichen Code hart codiert.

Typical usage::

    from scraper.config import BASE_URL, SELECTORS, CHROME_OPTIONS
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Projekt-Root (zwei Ebenen über dieser Datei)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# URLs & Pagination
# ---------------------------------------------------------------------------
BASE_URL: str = "https://www.immoscout24.ch/de/wohnung/mieten/ort-zuerich"
MAX_PAGES: int = 120
TARGET_ITEMS: int = 10_000

# ---------------------------------------------------------------------------
# CSS-Selektoren mit Fallback-Listen (Robustheit bei Layout-Änderungen)
# ---------------------------------------------------------------------------
SELECTORS: dict[str, list[str]] = {
    "listing_container": [
        "a[class*='HgCardElevated_content']",
        "a[class*='HgCardElevated']",
        "[class*='HgCardElevated']",
    ],
    "header_line": [
        "div > strong",
        "strong",
    ],
    "price": [
        "span",
    ],
    "address": [
        "address",
        "[class*='Address']",
    ],
    "title": [
        "p[class*='title'] span",
        "p span",
        "p[class*='HgCardElevated']",
    ],
    "next_page": [
        "a[aria-label='Zur nächsten Seite']",
        "a[aria-label='Nächste Seite']",
        "[class*='Pagination'] a[rel='next']",
    ],
    "cookie_accept": [
        "#onetrust-accept-btn-handler",
        "button.accept-all-cookies",
        "[data-testid='cookie-accept-all']",
    ],
}

# ---------------------------------------------------------------------------
# Chrome-Optionen (Headless-Modus, Anti-Detection)
# ---------------------------------------------------------------------------
CHROME_OPTIONS: list[str] = [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1920,1080",
    "--lang=de-CH",
]

USER_AGENTS: list[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
]

# ---------------------------------------------------------------------------
# Timing & Retry
# ---------------------------------------------------------------------------
SLEEP_MIN: float = 1.5
SLEEP_MAX: float = 3.5
PAGE_LOAD_TIMEOUT: int = 30
ELEMENT_WAIT_TIMEOUT: int = 15
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 2.0

# ---------------------------------------------------------------------------
# Output-Pfade (relativ zu PROJECT_ROOT)
# ---------------------------------------------------------------------------
OUTPUT_CSV: str = "data/immoscout_listings.csv"
LOG_FILE: str = "data/scraper.log"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# CSV-Schema (Datenfelder)
# ---------------------------------------------------------------------------
CSV_COLUMNS: list[str] = [
    "listing_id",
    "url",
    "title",
    "price_chf",
    "rooms",
    "area_m2",
    "price_per_m2",
    "address",
    "zip_code",
    "city",
    "floor",
    "available_from",
    "scraped_at",
]
