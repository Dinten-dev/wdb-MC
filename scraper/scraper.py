"""Main scraper module for ImmoScout24 rental listings.

Provides the ImmoscoutScraper class that automates browsing,
extraction, and persistence of apartment listing data from
immoscout24.ch using Selenium WebDriver.

Typical usage::

    with ImmoscoutScraper(headless=True) as scraper:
        df = scraper.run()
        scraper.save(df)
"""

import logging
import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from scraper import config
from scraper.utils import (
    clean_area,
    clean_price,
    clean_rooms,
    extract_listing_id,
    extract_zip,
    setup_logging,
    try_extract,
    validate_listing,
)

logger = logging.getLogger("immoscout-scraper")


class ImmoscoutScraper:
    """Selenium-based scraper for ImmoScout24 rental listings.

    Navigates immoscout24.ch search results, extracts listing data
    from each page, handles pagination, and exports results as CSV.
    Implements anti-detection measures and retry logic for robustness.

    Attributes:
        headless: Whether to run Chrome in headless mode.
        max_pages: Maximum number of result pages to scrape.
        target_items: Target number of listings to collect.
        driver: Selenium Chrome WebDriver instance (None until __enter__).
    """

    def __init__(
        self,
        headless: bool = True,
        max_pages: int = config.MAX_PAGES,
        target_items: int = config.TARGET_ITEMS,
    ) -> None:
        """Initialize the scraper with configuration parameters.

        Args:
            headless: Run Chrome in headless mode. Defaults to True.
            max_pages: Maximum result pages to scrape.
            target_items: Target listing count to collect.
        """
        self.headless = headless
        self.max_pages = max_pages
        self.target_items = target_items
        self.driver: webdriver.Chrome | None = None
        self._logger = setup_logging(config.LOG_FILE)

    def __enter__(self) -> "ImmoscoutScraper":
        """Enter context manager and initialize the WebDriver.

        Returns:
            The scraper instance with an active WebDriver.
        """
        self._init_driver()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        """Exit context manager and quit the WebDriver.

        Args:
            exc_type: Exception type, if any.
            exc_val: Exception value, if any.
            exc_tb: Exception traceback, if any.

        Returns:
            False to propagate any exceptions.
        """
        if self.driver is not None:
            self.driver.quit()
            self._logger.info("Driver closed.")
        return False

    def _init_driver(self) -> webdriver.Chrome:
        """Initialize and configure the Chrome WebDriver.

        Sets up Chrome with anti-detection options, a random user agent,
        and removes the navigator.webdriver property to avoid bot detection.
        Uses webdriver-manager for automatic ChromeDriver management.

        Returns:
            Configured Chrome WebDriver instance.
        """
        options = webdriver.ChromeOptions()

        for opt in config.CHROME_OPTIONS:
            if not self.headless and "headless" in opt:
                continue
            options.add_argument(opt)

        user_agent = random.choice(config.USER_AGENTS)
        options.add_argument(f"--user-agent={user_agent}")

        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        # Remove navigator.webdriver flag to avoid bot detection
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(navigator, 'webdriver', "
                    "{get: () => undefined})"
                )
            },
        )

        self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
        self._logger.info("Driver initialized with headless=%s", self.headless)

        return self.driver

    def _accept_cookies(self) -> None:
        """Attempt to accept the cookie consent banner.

        Tries each CSS selector from the cookie_accept fallback list.
        This method never raises — the cookie banner is optional.
        """
        cookie_wait_timeout = 5

        for selector in config.SELECTORS["cookie_accept"]:
            try:
                button = WebDriverWait(self.driver, cookie_wait_timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                button.click()
                self._logger.info(
                    "Cookie banner accepted via selector: %s", selector
                )
                return
            except (TimeoutException, NoSuchElementException, WebDriverException):
                continue

        self._logger.info("No cookie banner found, continuing.")

    def _wait_for_listings(self) -> bool:
        """Wait for listing elements to appear on the current page.

        Tries each CSS selector from the listing_container fallback list
        until one successfully locates at least one element.

        Returns:
            True if listings were found, False on timeout.
        """
        for selector in config.SELECTORS["listing_container"]:
            try:
                WebDriverWait(self.driver, config.ELEMENT_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return True
            except TimeoutException:
                continue

        self._logger.warning("Timeout waiting for listings on current page.")
        return False

    def _extract_single_listing(self, element: WebElement) -> dict | None:
        """Extract structured data from a single listing WebElement.

        The ImmoScout24 listing card embeds rooms, area, and price as
        separate ``<strong>`` and ``<span>`` elements within the card.
        The URL is the ``href`` attribute of the card ``<a>`` element
        itself. Title and address have dedicated child elements.

        Args:
            element: A WebElement representing one listing card (an ``<a>`` tag).

        Returns:
            A dict with all CSV_COLUMNS keys if valid, or None if
            the listing fails validation (missing url or title).
        """
        raw_title = try_extract(element, config.SELECTORS["title"])
        raw_address = try_extract(element, config.SELECTORS["address"])

        # URL is the href of the card element itself (it's an <a> tag)
        url = element.get_attribute("href")

        # Rooms and area come from <strong> tags (e.g. "1.5 Zimmer", "24m²")
        raw_rooms: str | None = None
        raw_area: str | None = None
        raw_price: str | None = None

        for selector in config.SELECTORS["header_line"]:
            try:
                strong_elements = element.find_elements(By.CSS_SELECTOR, selector)
                for strong_el in strong_elements:
                    text = strong_el.text.strip()
                    if not text:
                        continue
                    if "Zimmer" in text or "Zi." in text:
                        raw_rooms = text
                    elif "m²" in text or "m2" in text:
                        raw_area = text
                break
            except NoSuchElementException:
                continue

        # Price comes from <span> elements containing "CHF"
        for selector in config.SELECTORS["price"]:
            try:
                span_elements = element.find_elements(By.CSS_SELECTOR, selector)
                for span_el in span_elements:
                    text = span_el.text.strip()
                    if "CHF" in text:
                        raw_price = text
                        break
                if raw_price:
                    break
            except NoSuchElementException:
                continue

        price_chf = clean_price(raw_price)
        rooms = clean_rooms(raw_rooms)
        area_m2 = clean_area(raw_area)
        zip_code = extract_zip(raw_address)
        listing_id = extract_listing_id(url)

        # Compute price per square meter
        price_per_m2: float | None = None
        if price_chf is not None and area_m2 is not None and area_m2 > 0:
            price_per_m2 = round(price_chf / area_m2, 2)

        # Extract city name from address (text after ZIP code)
        city: str | None = None
        if raw_address and zip_code:
            parts = raw_address.split(zip_code)
            if len(parts) > 1 and parts[1].strip():
                city = parts[1].strip().strip(",").strip()

        listing: dict = {
            "listing_id": listing_id,
            "url": url,
            "title": raw_title,
            "price_chf": price_chf,
            "rooms": rooms,
            "area_m2": area_m2,
            "price_per_m2": price_per_m2,
            "address": raw_address,
            "zip_code": zip_code,
            "city": city,
            "floor": None,
            "available_from": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        if not validate_listing(listing):
            return None

        return listing

    def _scrape_page(self, page_num: int) -> list[dict]:
        """Scrape all listings from the current page.

        Finds listing container elements using fallback selectors,
        then extracts data from each one individually.

        Args:
            page_num: Current page number (for logging).

        Returns:
            List of listing dicts. Empty list if no elements found.
        """
        elements: list[WebElement] = []

        for selector in config.SELECTORS["listing_container"]:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    elements = found
                    break
            except NoSuchElementException:
                continue

        if not elements:
            self._logger.warning(
                "No listing elements found on page %d.", page_num
            )
            return []

        listings: list[dict] = []

        for element in elements:
            try:
                listing = self._extract_single_listing(element)
                if listing is not None:
                    listings.append(listing)
            except StaleElementReferenceException:
                self._logger.warning(
                    "Stale element on page %d, skipping listing.", page_num
                )
                continue

        self._logger.info(
            "Page %d: scraped %d listings.", page_num, len(listings)
        )
        return listings

    def _navigate_to_next_page(self) -> bool:
        """Navigate to the next results page.

        Finds and clicks the next-page button, then waits for the page
        content to refresh by checking staleness of a current element.

        Returns:
            True if navigation succeeded, False if no next page
            exists or an error occurred.
        """
        # Get a reference element to detect page transition
        reference_element: WebElement | None = None
        for selector in config.SELECTORS["listing_container"]:
            try:
                reference_element = self.driver.find_element(
                    By.CSS_SELECTOR, selector
                )
                break
            except NoSuchElementException:
                continue

        for selector in config.SELECTORS["next_page"]:
            try:
                button = WebDriverWait(
                    self.driver, config.ELEMENT_WAIT_TIMEOUT
                ).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )

                # Scroll button into view before clicking
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);", button
                )

                button.click()

                # Wait for page content to refresh
                if reference_element is not None:
                    WebDriverWait(
                        self.driver, config.ELEMENT_WAIT_TIMEOUT
                    ).until(EC.staleness_of(reference_element))

                return True

            except (TimeoutException, NoSuchElementException):
                continue
            except WebDriverException as exc:
                self._logger.warning("Navigation error: %s", exc)
                return False

        return False

    def _with_retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        max_retries: int = config.MAX_RETRIES,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with exponential backoff retry logic.

        Args:
            func: The callable to execute.
            *args: Positional arguments passed to func.
            max_retries: Maximum number of retry attempts.
            **kwargs: Keyword arguments passed to func.

        Returns:
            The return value of func on success.

        Raises:
            Exception: The last exception if all retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (WebDriverException, TimeoutException, OSError) as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    wait_time = config.RETRY_BACKOFF_BASE ** attempt
                    self._logger.warning(
                        "Retry %d/%d for %s: %s (waiting %.1fs)",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        exc,
                        wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    self._logger.error(
                        "All %d retries exhausted for %s: %s",
                        max_retries,
                        func.__name__,
                        exc,
                    )

        raise last_exception  # type: ignore[misc]

    def run(self) -> pd.DataFrame:
        """Execute the full scraping workflow.

        Opens the search page, accepts cookies, then iterates through
        result pages collecting listing data until the target count
        is reached or no more pages are available.

        Returns:
            A pandas DataFrame with deduplicated listing data,
            columns matching config.CSV_COLUMNS.
        """
        self._with_retry(self.driver.get, config.BASE_URL)
        self._accept_cookies()

        all_listings: list[dict] = []
        page_num = 1

        while (
            page_num <= self.max_pages
            and len(all_listings) < self.target_items
        ):
            if not self._wait_for_listings():
                self._logger.warning(
                    "No listings on page %d, stopping.", page_num
                )
                break

            page_listings = self._scrape_page(page_num)
            all_listings.extend(page_listings)

            if page_num % 10 == 0:
                self._logger.info(
                    "Progress: %s / %s collected (page %d).",
                    f"{len(all_listings):,}",
                    f"{self.target_items:,}",
                    page_num,
                )

            if not self._navigate_to_next_page():
                self._logger.info(
                    "No next page after page %d, stopping.", page_num
                )
                break

            sleep_duration = random.uniform(config.SLEEP_MIN, config.SLEEP_MAX)
            time.sleep(sleep_duration)

            page_num += 1

        # Deduplicate by URL
        df = pd.DataFrame(all_listings, columns=config.CSV_COLUMNS)
        initial_count = len(df)
        df = df.drop_duplicates(subset=["url"], keep="first")

        if initial_count > len(df):
            self._logger.info(
                "Removed %d duplicate listings.", initial_count - len(df)
            )

        self._logger.info(
            "Scraping complete: %s unique listings collected.",
            f"{len(df):,}",
        )

        return df

    def save(self, df: pd.DataFrame) -> None:
        """Save the DataFrame to CSV.

        Creates the output directory if it doesn't exist and writes
        the data with UTF-8-BOM encoding for Excel compatibility.

        Args:
            df: DataFrame with listing data to save.
        """
        output_path = Path(config.OUTPUT_CSV)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        self._logger.info(
            "Saved %s rows x %d columns to %s.",
            f"{len(df):,}",
            len(df.columns),
            config.OUTPUT_CSV,
        )


if __name__ == "__main__":
    with ImmoscoutScraper() as scraper:
        result_df = scraper.run()
        scraper.save(result_df)
        logger.info(
            "Done. %d listings saved to %s.",
            len(result_df),
            config.OUTPUT_CSV,
        )
