"""Unit tests for scraper.scraper using mocks for Selenium WebDriver."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from selenium.common.exceptions import NoSuchElementException

from scraper.scraper import ImmoscoutScraper


class TestScraperInit:
    """Tests for ImmoscoutScraper initialization."""

    def test_scraper_default_values(self) -> None:
        """Verify default parameter values on construction."""
        scraper = ImmoscoutScraper()
        assert scraper.headless is True
        assert scraper.max_pages > 0
        assert scraper.target_items == 10_000
        assert scraper.driver is None

    def test_scraper_custom_params(self) -> None:
        """Verify that custom parameters are stored correctly."""
        scraper = ImmoscoutScraper(
            headless=False, max_pages=5, target_items=100
        )
        assert scraper.headless is False
        assert scraper.max_pages == 5
        assert scraper.target_items == 100


class TestCookieHandling:
    """Tests for cookie banner acceptance logic."""

    def test_accept_cookies_no_banner(self) -> None:
        """Verify that _accept_cookies does not raise when no banner exists.

        A mock driver whose find_element always raises simulates
        a page without a cookie consent banner.
        """
        scraper = ImmoscoutScraper()
        mock_driver = MagicMock()
        mock_driver.find_element.side_effect = NoSuchElementException()
        scraper.driver = mock_driver

        # Must not raise — cookie banner is optional
        scraper._accept_cookies()


class TestExtraction:
    """Tests for listing extraction logic."""

    def test_extract_single_listing_invalid_element(self) -> None:
        """Verify that an element yielding no url/title returns None.

        A mock element whose find_element always raises simulates
        an empty or broken listing card.
        """
        scraper = ImmoscoutScraper()
        mock_element = MagicMock()
        mock_element.find_element.side_effect = NoSuchElementException()
        mock_element.find_elements.return_value = []
        mock_element.get_attribute.return_value = None

        result = scraper._extract_single_listing(mock_element)
        assert result is None


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_quits_driver(self) -> None:
        """Verify that __exit__ calls driver.quit() exactly once."""
        scraper = ImmoscoutScraper()
        mock_driver = MagicMock()
        scraper.driver = mock_driver

        scraper.__exit__(None, None, None)

        mock_driver.quit.assert_called_once()
