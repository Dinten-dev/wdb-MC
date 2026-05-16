"""Utility functions for parsing, cleaning, logging, and validation."""

import copy
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from scraper import config

logger = logging.getLogger(__name__)

# Pre-compiled patterns for time string parsing
_TIME_HOURS_PATTERN = re.compile(r"(\d+)\s*h", re.IGNORECASE)
_TIME_MINUTES_PATTERN = re.compile(r"(\d+)\s*m", re.IGNORECASE)


def setup_logging(log_file: str = config.LOG_FILE) -> logging.Logger:
    """Configure root logger with console and file handlers.

    Args:
        log_file: Path to the log file relative to project root.

    Returns:
        The configured root logger instance.
    """
    log_path = config.PROJECT_ROOT / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return root_logger


def parse_time_string(raw: str | None) -> float | None:
    """Parse a time string like '12h', '1h 30m', '45m' into decimal hours.

    Handles formats used in HowLongToBeat displays. Returns None for
    values that indicate no data ('--', '0', None, empty string).

    Args:
        raw: Raw time string from the API or page.

    Returns:
        Decimal hours as float, or None if unparsable or missing.
    """
    if raw is None or not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned or cleaned in ("--", "0", "N/A", "—"):
        return None

    hours = 0.0
    h_match = _TIME_HOURS_PATTERN.search(cleaned)
    m_match = _TIME_MINUTES_PATTERN.search(cleaned)

    if h_match:
        hours += float(h_match.group(1))
    if m_match:
        hours += float(m_match.group(1)) / 60.0

    if h_match or m_match:
        return round(hours, 2)

    # Fallback: try parsing as a plain number (already in hours)
    try:
        val = float(cleaned)
        return round(val, 2) if val > 0 else None
    except ValueError:
        return None


def seconds_to_hours(seconds: int | float | None) -> float | None:
    """Convert API time values from seconds to decimal hours.

    The HLTB API returns completion times in seconds. A value of 0
    indicates no data and is converted to None.

    Args:
        seconds: Time in seconds from the API, or None.

    Returns:
        Decimal hours rounded to 2 places, or None for missing data.
    """
    if seconds is None or seconds == 0:
        return None

    try:
        val = float(seconds)
        return round(val / 3600.0, 2) if val > 0 else None
    except (ValueError, TypeError):
        return None


def extract_game_id(url: str | None) -> str | None:
    """Extract the numeric game ID from a HLTB game URL.

    Args:
        url: Full URL like 'https://howlongtobeat.com/game/12345'.

    Returns:
        The numeric ID as string, or None if not extractable.
    """
    if not url or not isinstance(url, str):
        return None

    match = re.search(r"/game/(\d+)", url)
    return match.group(1) if match else None


def validate_game(game: dict) -> bool:
    """Validate that a game dict has the minimum required fields.

    A valid game must have a non-empty game_id and title.

    Args:
        game: Dictionary with game data fields.

    Returns:
        True if the game has required fields, False otherwise.
    """
    game_id = game.get("game_id")
    title = game.get("title")
    return bool(game_id) and bool(title)


def with_retry(
    func: Any,
    *args: Any,
    max_retries: int = config.MAX_RETRIES,
    backoff_base: float = config.RETRY_BACKOFF_BASE,
    **kwargs: Any,
) -> Any:
    """Execute a callable with exponential backoff retry logic.

    Handles ConnectionError, Timeout, and HTTPError with status-specific
    recovery strategies. A 429 (rate limited) response triggers a longer
    sleep before retrying.

    Args:
        func: The callable to execute.
        *args: Positional arguments for func.
        max_retries: Maximum retry attempts.
        backoff_base: Base multiplier for exponential backoff.
        **kwargs: Keyword arguments for func.

    Returns:
        The return value of func on success.

    Raises:
        Exception: The last exception if all retries are exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as exc:
            last_exception = exc
            if exc.response is not None and exc.response.status_code == 429:
                # Rate limited — wait longer before retrying
                wait_time = config.RATE_LIMIT_SLEEP
                logger.warning(
                    "Rate limited (429), waiting %.1fs before retry %d/%d",
                    wait_time,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    "HTTP error %s, retry %d/%d (waiting %.1fs)",
                    exc,
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                time.sleep(wait_time)
            else:
                logger.error("All %d retries exhausted for %s: %s", max_retries, func.__name__, exc)
        except requests.exceptions.Timeout as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    "Timeout for %s, retry %d/%d (waiting %.1fs)",
                    func.__name__,
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                time.sleep(wait_time)
            else:
                logger.error("All %d retries exhausted for %s: %s", max_retries, func.__name__, exc)
        except requests.exceptions.ConnectionError as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                wait_time = backoff_base ** (attempt + 1)
                logger.warning(
                    "Connection error for %s, retry %d/%d (waiting %.1fs)",
                    func.__name__,
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                time.sleep(wait_time)
            else:
                logger.error("All %d retries exhausted for %s: %s", max_retries, func.__name__, exc)
        except (OSError, ValueError) as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    "Error in %s: %s, retry %d/%d (waiting %.1fs)",
                    func.__name__,
                    exc,
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                time.sleep(wait_time)
            else:
                logger.error("All %d retries exhausted for %s: %s", max_retries, func.__name__, exc)

    raise last_exception  # type: ignore[misc]


def build_search_payload(page: int = 1, search_terms: list[str] | None = None) -> dict:
    """Build the POST payload for the HLTB search API.

    Args:
        page: Page number for pagination (1-indexed).
        search_terms: List of search terms. Empty list browses all.

    Returns:
        Deep-copied payload dict ready for JSON serialisation.
    """
    payload = copy.deepcopy(config.SEARCH_PAYLOAD_TEMPLATE)
    payload["searchPage"] = page
    payload["searchTerms"] = search_terms if search_terms is not None else []
    return payload


def resolve_search_url(user_agent: str) -> tuple[str, dict[str, str]]:
    """Resolve the dynamic search URL and auth token from the HLTB homepage.

    HLTB embeds the search endpoint path in a JS bundle and requires
    an auth token obtained from an init endpoint. This function
    replicates the discovery process used by howlongtobeatpy.

    Args:
        user_agent: User-Agent string for the requests.

    Returns:
        Tuple of (search_url, extra_headers) where extra_headers may
        contain auth tokens if successfully obtained.
    """
    headers = {"User-Agent": user_agent, "Referer": config.REFERER_HEADER}
    extra_headers: dict[str, str] = {}
    search_url = config.SEARCH_URL

    try:
        resp = requests.get(config.BASE_URL, headers=headers, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("Failed to fetch homepage for URL discovery: %d", resp.status_code)
            return search_url, extra_headers

        soup = BeautifulSoup(resp.text, "html.parser")
        scripts = soup.find_all("script", src=True)
        app_scripts = [s["src"] for s in scripts if "_app-" in s["src"]]
        all_scripts = [s["src"] for s in scripts] if not app_scripts else app_scripts

        for script_src in all_scripts:
            full_url = config.BASE_URL + script_src.lstrip("/")
            script_resp = requests.get(full_url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            if script_resp.status_code != 200:
                continue

            # Extract the search endpoint from the JS bundle
            pattern = re.compile(
                r'fetch\s*\(\s*["\']\/api\/([a-zA-Z0-9_/]+)[^"\']*["\']\s*,\s*\{[^}]*method:\s*["\']POST["\'][^}]*\}',
                re.DOTALL | re.IGNORECASE,
            )
            match = pattern.search(script_resp.text)
            if match:
                path_suffix = match.group(1).split("/")[0]
                search_url = f"{config.BASE_URL}api/{path_suffix}/"
                logger.info("Discovered search URL: %s", search_url)
                break

        # Attempt to get auth token
        auth_url = f"{config.BASE_URL}api/s/init"
        ts_params = {"t": str(int(time.time() * 1000))}
        auth_resp = requests.get(
            auth_url, params=ts_params, headers=headers, timeout=config.REQUEST_TIMEOUT
        )
        if auth_resp.status_code == 200:
            try:
                auth_data = auth_resp.json()
                if "token" in auth_data:
                    extra_headers["x-auth-token"] = str(auth_data["token"])
                if "key" in auth_data and "value" in auth_data:
                    extra_headers["x-hp-key"] = str(auth_data["key"])
                    extra_headers["x-hp-val"] = str(auth_data["value"])
                logger.info("Auth token obtained successfully")
            except ValueError:
                logger.warning("Auth endpoint returned non-JSON response")

    except requests.exceptions.RequestException as exc:
        logger.warning("URL discovery failed, using defaults: %s", exc)

    return search_url, extra_headers


def current_utc_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format.

    Returns:
        ISO 8601 timestamp string with timezone info.
    """
    return datetime.now(UTC).isoformat()
