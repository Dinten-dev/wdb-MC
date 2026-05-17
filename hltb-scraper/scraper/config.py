"""Centralised configuration constants for the HowLongToBeat scraper."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (one level above this file's parent)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# HLTB API configuration
# ---------------------------------------------------------------------------
BASE_URL: str = "https://howlongtobeat.com/"
SEARCH_API_PATH: str = "api/s/"
SEARCH_URL: str = BASE_URL + SEARCH_API_PATH
GAME_PAGE_URL: str = BASE_URL + "game/"
REFERER_HEADER: str = BASE_URL

# ---------------------------------------------------------------------------
# Search payload defaults
# ---------------------------------------------------------------------------
SEARCH_PAGE_SIZE: int = 20
MAX_PAGES: int = 600
TARGET_ITEMS: int = 10_000

SEARCH_PAYLOAD_TEMPLATE: dict = {
    "searchType": "games",
    "searchTerms": [],
    "searchPage": 1,
    "size": SEARCH_PAGE_SIZE,
    "searchOptions": {
        "games": {
            "userId": 0,
            "platform": "",
            "sortCategory": "popular",
            "rangeCategory": "main",
            "rangeTime": {"min": 0, "max": 0},
            "gameplay": {
                "perspective": "",
                "flow": "",
                "genre": "",
                "difficulty": "",
            },
            "rangeYear": {"max": "", "min": ""},
            "modifier": "",
        },
        "users": {"sortCategory": "postcount"},
        "lists": {"sortCategory": "follows"},
    },
    "useCache": True,
}

# ---------------------------------------------------------------------------
# Request headers
# ---------------------------------------------------------------------------
REQUEST_HEADERS: dict[str, str] = {
    "content-type": "application/json",
    "accept": "*/*",
    "Referer": REFERER_HEADER,
    "Origin": REFERER_HEADER,
}

# User-Agent identifying the scraper per ethical scraping guidelines
SCRAPER_USER_AGENT: str = (
    "FHNW-WDB-Scraper/1.0 (academic project; contact: student@students.fhnw.ch)"
)

# ---------------------------------------------------------------------------
# Selenium detail page selectors (fallback lists for robustness)
# ---------------------------------------------------------------------------
DETAIL_SELECTORS: dict[str, list[str]] = {
    "title": [
        "div.GameHeader_profile_header__q_PID h1",
        ".GameHeader_profile_header__q_PID h1",
        "h1",
    ],
    "developer": [
        "div.GameSummary_profile_info__HZFQu a",
        ".GameSummary_profile_info__HZFQu a",
        "div.GameSummary_profile_info a",
    ],
    "genres": [
        "div.GameSummary_profile_info__HZFQu span",
        ".GameSummary_profile_info__HZFQu span",
        "div.GameSummary_profile_info span",
    ],
    "platforms": [
        "div.GameSummary_profile_info__HZFQu span",
        ".GameSummary_profile_info__HZFQu span",
    ],
    "release_date": [
        "div.GameSummary_profile_info__HZFQu",
        ".GameSummary_profile_info__HZFQu",
    ],
}

# ---------------------------------------------------------------------------
# Chrome options for Selenium detail enrichment
# ---------------------------------------------------------------------------
CHROME_OPTIONS: list[str] = [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1920,1080",
]

# ---------------------------------------------------------------------------
# Timing & retry
# ---------------------------------------------------------------------------
SLEEP_MIN: float = 0.3
SLEEP_MAX: float = 1.0
DETAIL_SLEEP_MIN: float = 1.5
DETAIL_SLEEP_MAX: float = 3.0
PAGE_LOAD_TIMEOUT: int = 30
ELEMENT_WAIT_TIMEOUT: int = 10
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 2.0
REQUEST_TIMEOUT: int = 30
RATE_LIMIT_SLEEP: float = 30.0

# Detail enrichment sample size
DETAIL_SAMPLE_SIZE: int = 200

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
OUTPUT_CSV: str = "data/hltb_games.csv"
LOG_FILE: str = "data/scraper.log"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# CSV schema
# ---------------------------------------------------------------------------
CSV_COLUMNS: list[str] = [
    "game_id",
    "title",
    "game_type",
    "platform",
    "genre",
    "developer",
    "release_year",
    "main_story_hours",
    "main_plus_extras_hours",
    "completionist_hours",
    "all_styles_hours",
    "review_score",
    "count_playing",
    "count_backlog",
    "count_retired",
    "count_comp",
    "count_review",
    "similarity_score",
    "scraped_at",
    "source_page",
]

# ---------------------------------------------------------------------------
# robots.txt contents (checked 2025-05-16, returns 403 — no specific
# Disallow directives are served, site relies on Cloudflare protection)
# ---------------------------------------------------------------------------
ROBOTS_TXT_NOTE: str = (
    "howlongtobeat.com returns HTTP 403 for /robots.txt as of 2025-05-16. "
    "No explicit Disallow directives are published. The scraper respects "
    "rate limits and collects only public aggregate game metadata."
)
