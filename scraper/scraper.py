"""Main scraper module with requests-based bulk collection and Selenium detail enrichment."""

import json
import logging
import random
import time
from pathlib import Path

import pandas as pd
from howlongtobeatpy.HTMLRequests import HTMLRequests, SearchModifiers
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from scraper import config
from scraper.utils import (
    current_utc_iso,
    seconds_to_hours,
    setup_logging,
    validate_game,
    with_retry,
)

logger = logging.getLogger(__name__)


class HLTBScraper:
    """Hybrid scraper for HowLongToBeat game completion time data.

    Uses two complementary components:
    1. A requests-based bulk collector that paginates through the
       HLTB internal JSON API (via howlongtobeatpy) to gather 10,000+
       game entries efficiently using POST requests.
    2. A Selenium-based detail enricher that visits individual game
       pages to extract additional fields like developer and genre
       for a sample of listings.

    Attributes:
        max_pages: Maximum search result pages to iterate.
        target_items: Target number of unique games to collect.
        driver: Selenium Chrome WebDriver (initialised only for enrichment).
    """

    def __init__(
        self,
        max_pages: int = config.MAX_PAGES,
        target_items: int = config.TARGET_ITEMS,
        headless: bool = True,
    ) -> None:
        """Initialise the scraper with configuration parameters.

        Args:
            max_pages: Maximum result pages to scrape via the API.
            target_items: Target listing count to collect.
            headless: Run Selenium Chrome in headless mode.
        """
        self.max_pages = max_pages
        self.target_items = target_items
        self.headless = headless
        self.driver: webdriver.Chrome | None = None
        self._logger = setup_logging()

    def __enter__(self) -> "HLTBScraper":
        """Enter context manager.

        Returns:
            The scraper instance ready for use.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        """Exit context manager and close the Selenium driver if open.

        Args:
            exc_type: Exception type, if any.
            exc_val: Exception value, if any.
            exc_tb: Exception traceback, if any.

        Returns:
            False to propagate any exceptions.
        """
        if self.driver is not None:
            self.driver.quit()
            logger.info("Selenium driver closed.")
        return False

    def _fetch_search_page(self, page: int) -> list[dict]:
        """Fetch a single page of search results via the HLTB internal API.

        Uses howlongtobeatpy's HTMLRequests to handle dynamic URL
        resolution and auth token management. The response is a JSON
        string containing game entries under the 'data' key.

        Args:
            page: Page number to fetch (1-indexed).

        Returns:
            List of raw game dicts from the API response.

        Raises:
            ValueError: If the response is not valid JSON.
        """
        raw_response = HTMLRequests.send_web_request(
            game_name="",
            search_modifiers=SearchModifiers.NONE,
            page=page,
        )

        if raw_response is None:
            logger.warning("API returned None for page %d.", page)
            return []

        # Detect HTML error pages returned during rate limiting
        if raw_response.strip().startswith("<"):
            logger.warning(
                "API returned HTML instead of JSON on page %d (possible rate limit). "
                "Content starts with: %s",
                page,
                raw_response[:100],
            )
            raise ValueError("API returned HTML instead of JSON")

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error on page %d: %s", page, exc)
            logger.debug("Raw response: %s", raw_response[:500])
            raise ValueError("Invalid JSON response") from exc

        if "data" not in data:
            logger.warning(
                "Unexpected API response structure on page %d. Keys: %s",
                page,
                list(data.keys()),
            )
            logger.debug("Raw response body: %s", json.dumps(data)[:500])
            return []

        return data["data"]

    def _parse_game_entry(self, raw: dict, page: int) -> dict | None:
        """Parse a raw API game entry into a structured dict.

        Uses .get() with None defaults for all field access so that
        missing fields never cause crashes. Times are converted from
        seconds to hours.

        Args:
            raw: Raw game dict from the API response.
            page: Page number this game was found on.

        Returns:
            Parsed game dict matching CSV_COLUMNS, or None if invalid.
        """
        game = {
            "game_id": raw.get("game_id"),
            "title": raw.get("game_name"),
            "game_type": raw.get("game_type"),
            "platform": raw.get("profile_platform"),
            "genre": None,
            "developer": raw.get("profile_dev"),
            "release_year": raw.get("release_world"),
            "main_story_hours": seconds_to_hours(raw.get("comp_main")),
            "main_plus_extras_hours": seconds_to_hours(raw.get("comp_plus")),
            "completionist_hours": seconds_to_hours(raw.get("comp_100")),
            "all_styles_hours": seconds_to_hours(raw.get("comp_all")),
            "review_score": raw.get("review_score"),
            "count_playing": raw.get("count_playing"),
            "count_backlog": raw.get("count_backlog"),
            "count_retired": raw.get("count_retired"),
            "count_comp": raw.get("count_comp"),
            "count_review": raw.get("count_review"),
            "similarity_score": None,
            "scraped_at": current_utc_iso(),
            "source_page": page,
        }

        if not validate_game(game):
            return None

        return game

    def collect_bulk(self) -> list[dict]:
        """Collect game data in bulk using the requests-based API client.

        Paginates through search results until the target count is
        reached or no more results are returned.

        Returns:
            List of parsed game dicts.
        """
        all_games: list[dict] = []
        seen_ids: set[int] = set()
        consecutive_empty = 0
        max_consecutive_empty = 3

        for page in range(1, self.max_pages + 1):
            if len(all_games) >= self.target_items:
                logger.info(
                    "Target of %s items reached at page %d.",
                    f"{self.target_items:,}",
                    page,
                )
                break

            try:
                raw_games = with_retry(self._fetch_search_page, page)
            except (ValueError, OSError, Exception) as exc:
                logger.error("Failed to fetch page %d after retries: %s", page, exc)
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    logger.warning("Stopping after %d consecutive failures.", max_consecutive_empty)
                    break
                continue

            if not raw_games:
                consecutive_empty += 1
                logger.info("Empty results on page %d (%d consecutive).", page, consecutive_empty)
                if consecutive_empty >= max_consecutive_empty:
                    logger.info("No more results. Stopping at page %d.", page)
                    break
                continue

            consecutive_empty = 0
            page_count = 0

            for raw in raw_games:
                game = self._parse_game_entry(raw, page)
                if game is None:
                    continue
                gid = game["game_id"]
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
                all_games.append(game)
                page_count += 1

            logger.info(
                "Page %d: %d new games (total: %s).",
                page,
                page_count,
                f"{len(all_games):,}",
            )

            if page % 50 == 0:
                logger.info(
                    "Progress: %s / %s collected (page %d).",
                    f"{len(all_games):,}",
                    f"{self.target_items:,}",
                    page,
                )

            # Rate limiting: random sleep between requests
            sleep_duration = random.uniform(config.SLEEP_MIN, config.SLEEP_MAX)
            time.sleep(sleep_duration)

        logger.info("Bulk collection complete: %s unique games.", f"{len(all_games):,}")
        return all_games

    def _init_selenium(self) -> webdriver.Chrome:
        """Initialise the Selenium Chrome WebDriver for detail page enrichment.

        Returns:
            Configured Chrome WebDriver instance.
        """
        options = webdriver.ChromeOptions()
        for opt in config.CHROME_OPTIONS:
            if not self.headless and "headless" in opt:
                continue
            options.add_argument(opt)
        options.add_argument(f"--user-agent={config.SCRAPER_USER_AGENT}")

        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
        logger.info("Selenium driver initialised (headless=%s).", self.headless)
        return self.driver

    def _extract_detail_field(self, selector_key: str) -> str | None:
        """Extract a text field from the current detail page using fallback selectors.

        Args:
            selector_key: Key into config.DETAIL_SELECTORS.

        Returns:
            The extracted text, or None if not found.
        """
        selectors = config.DETAIL_SELECTORS.get(selector_key, [])
        for selector in selectors:
            try:
                el = WebDriverWait(self.driver, config.ELEMENT_WAIT_TIMEOUT).until(
                    ec.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                text = el.text.strip()
                if text:
                    return text
            except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
                continue
            except WebDriverException as exc:
                logger.debug("WebDriver error for selector '%s': %s", selector, exc)
                continue
        return None

    def _extract_detail_fields(self, element: WebElement | None = None) -> dict:
        """Extract detail fields from the current game detail page.

        Collects developer and genre from the rendered page using
        CSS selector fallbacks for robustness against layout changes.

        Args:
            element: Optional WebElement (unused, for test compatibility).

        Returns:
            Dict with 'developer' and 'genre' keys.
        """
        developer = self._extract_detail_field("developer")
        genre_text = self._extract_detail_field("genres")

        return {
            "developer": developer,
            "genre": genre_text,
        }

    def enrich_with_details(self, games: list[dict]) -> list[dict]:
        """Enrich a sample of games with detail page data via Selenium.

        Visits individual game pages to extract developer and genre
        information not available in the search API response.

        Args:
            games: Full list of collected games.

        Returns:
            The same list with enriched entries where possible.
        """
        sample_size = min(config.DETAIL_SAMPLE_SIZE, len(games))
        if sample_size == 0:
            return games

        self._init_selenium()
        sample_indices = random.sample(range(len(games)), sample_size)

        logger.info("Enriching %d games with detail page data.", sample_size)
        enriched_count = 0

        for idx in sample_indices:
            game = games[idx]
            game_url = f"{config.GAME_PAGE_URL}{game['game_id']}"

            try:
                self.driver.get(game_url)
                details = self._extract_detail_fields()

                if details.get("developer"):
                    game["developer"] = details["developer"]
                if details.get("genre"):
                    game["genre"] = details["genre"]
                enriched_count += 1

            except TimeoutException:
                logger.warning("Timeout loading detail page for game %s.", game["game_id"])
            except WebDriverException as exc:
                logger.warning("WebDriver error for game %s: %s", game["game_id"], exc)

            sleep_duration = random.uniform(config.DETAIL_SLEEP_MIN, config.DETAIL_SLEEP_MAX)
            time.sleep(sleep_duration)

        logger.info(
            "Detail enrichment complete: %d/%d games enriched.",
            enriched_count,
            sample_size,
        )
        return games

    def run(self) -> pd.DataFrame:
        """Execute the full scraping workflow.

        1. Collects games in bulk via the internal API (POST requests).
        2. Enriches a sample with Selenium detail data.
        3. Deduplicates and returns a DataFrame.

        Returns:
            DataFrame with deduplicated game data.
        """
        games = self.collect_bulk()

        if games:
            games = self.enrich_with_details(games)

        df = pd.DataFrame(games)

        # Ensure all expected columns exist
        for col in config.CSV_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df = df[config.CSV_COLUMNS]

        initial_count = len(df)
        df = df.drop_duplicates(subset=["game_id"], keep="first")
        if initial_count > len(df):
            logger.info("Removed %d duplicate entries.", initial_count - len(df))

        logger.info("Scraping complete: %s unique games collected.", f"{len(df):,}")
        return df

    def save(self, df: pd.DataFrame) -> None:
        """Save the DataFrame to CSV with UTF-8 BOM encoding.

        Args:
            df: DataFrame with game data to save.
        """
        output_path = Path(config.OUTPUT_CSV)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(
            "Saved %s rows × %d columns to %s.",
            f"{len(df):,}",
            len(df.columns),
            config.OUTPUT_CSV,
        )


if __name__ == "__main__":
    with HLTBScraper() as scraper:
        result_df = scraper.run()
        scraper.save(result_df)
        logger.info("Done. %d games saved to %s.", len(result_df), config.OUTPUT_CSV)
