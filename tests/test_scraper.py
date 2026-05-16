"""Integration tests for the HLTBScraper class using mocks."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from selenium.common.exceptions import TimeoutException

from scraper.scraper import HLTBScraper
from scraper.utils import with_retry


class TestScraperInit:
    """Tests for HLTBScraper initialisation."""

    def test_default_attributes(self) -> None:
        """Verify that the scraper initialises with correct defaults without network."""
        scraper = HLTBScraper()
        assert scraper.max_pages == 600
        assert scraper.target_items == 10_000
        assert scraper.headless is True
        assert scraper.driver is None

    def test_custom_attributes(self) -> None:
        """Verify that custom init parameters are stored correctly."""
        scraper = HLTBScraper(max_pages=10, target_items=100, headless=False)
        assert scraper.max_pages == 10
        assert scraper.target_items == 100
        assert scraper.headless is False


class TestRetryWrapper:
    """Tests for the with_retry utility function."""

    def test_retry_on_persistent_failure(self) -> None:
        """Verify retry calls the function the correct number of times before raising."""
        mock_func = MagicMock(side_effect=requests.exceptions.ConnectionError("fail"))
        mock_func.__name__ = "mock_func"

        with pytest.raises(requests.exceptions.ConnectionError):
            with_retry(mock_func, max_retries=3, backoff_base=0.01)

        assert mock_func.call_count == 3

    def test_retry_succeeds_on_second_attempt(self) -> None:
        """Verify retry returns the result when the function eventually succeeds."""
        mock_func = MagicMock(side_effect=[requests.exceptions.Timeout("slow"), "success"])
        mock_func.__name__ = "mock_func"

        result = with_retry(mock_func, max_retries=3, backoff_base=0.01)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_no_retry_on_success(self) -> None:
        """Verify the function is called exactly once on immediate success."""
        mock_func = MagicMock(return_value="ok")
        mock_func.__name__ = "mock_func"

        result = with_retry(mock_func, max_retries=3, backoff_base=0.01)

        assert result == "ok"
        assert mock_func.call_count == 1


class TestParseGameEntry:
    """Tests for _parse_game_entry."""

    def test_valid_entry(self) -> None:
        """Verify a complete API response entry is correctly parsed."""
        scraper = HLTBScraper()
        raw = {
            "game_id": 38019,
            "game_name": "Zelda: Breath of the Wild",
            "game_type": "game",
            "profile_platform": "Nintendo Switch",
            "profile_dev": "Nintendo",
            "release_world": 2017,
            "comp_main": 181224,
            "comp_plus": 354348,
            "comp_100": 697032,
            "comp_all": 333720,
            "review_score": 93,
            "count_playing": 500,
            "count_backlog": 1000,
            "count_retired": 200,
            "count_comp": 3000,
            "count_review": 150,
        }

        result = scraper._parse_game_entry(raw, page=1)

        assert result is not None
        assert result["game_id"] == 38019
        assert result["title"] == "Zelda: Breath of the Wild"
        assert result["main_story_hours"] == 50.34
        assert result["source_page"] == 1

    def test_missing_fields(self) -> None:
        """Verify that entries with missing optional fields still parse."""
        scraper = HLTBScraper()
        raw = {
            "game_id": 99999,
            "game_name": "Unknown Game",
        }

        result = scraper._parse_game_entry(raw, page=5)

        assert result is not None
        assert result["main_story_hours"] is None
        assert result["review_score"] is None

    def test_invalid_entry(self) -> None:
        """Verify that an entry without a game name returns None."""
        scraper = HLTBScraper()
        result = scraper._parse_game_entry({}, page=1)
        assert result is None


class TestDetailExtraction:
    """Tests for Selenium detail page extraction."""

    def test_extract_detail_fields_no_driver(self) -> None:
        """Verify that _extract_detail_fields handles a mock driver with no elements."""
        scraper = HLTBScraper()
        mock_driver = MagicMock()
        mock_driver.find_element.side_effect = Exception("no element")
        scraper.driver = mock_driver

        # Mock WebDriverWait to raise TimeoutException for all selectors
        with patch("scraper.scraper.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.side_effect = TimeoutException("timeout")
            result = scraper._extract_detail_fields()

        assert result["developer"] is None
        assert result["genre"] is None
