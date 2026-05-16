"""Unit tests for scraper utility functions."""

import pytest

from scraper.utils import extract_game_id, parse_time_string, seconds_to_hours, validate_game


class TestParseTimeString:
    """Tests for the parse_time_string function."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("12h", 12.0),
            ("1h 30m", 1.5),
            ("45m", 0.75),
            ("0h 30m", 0.5),
            ("100h", 100.0),
            ("2h 15m", 2.25),
            ("5H 0M", 5.0),
            ("3.5", 3.5),
        ],
        ids=[
            "hours_only",
            "hours_and_minutes",
            "minutes_only",
            "zero_hours_with_minutes",
            "large_hours",
            "mixed",
            "uppercase",
            "plain_number",
        ],
    )
    def test_valid_inputs(self, raw: str, expected: float) -> None:
        """Verify that valid time strings parse to the correct decimal hours."""
        assert parse_time_string(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, "", "--", "0", "N/A", "—", "no data"],
        ids=["none", "empty", "dashes", "zero", "na", "em_dash", "text"],
    )
    def test_invalid_inputs(self, raw: str | None) -> None:
        """Verify that invalid or missing time values return None."""
        assert parse_time_string(raw) is None


class TestSecondsToHours:
    """Tests for seconds_to_hours conversion."""

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (3600, 1.0),
            (5400, 1.5),
            (7200, 2.0),
            (180000, 50.0),
            (0, None),
            (None, None),
        ],
        ids=["one_hour", "ninety_minutes", "two_hours", "fifty_hours", "zero", "none"],
    )
    def test_conversion(self, seconds: int | None, expected: float | None) -> None:
        """Verify seconds-to-hours conversion with known values."""
        assert seconds_to_hours(seconds) == expected


class TestExtractGameId:
    """Tests for the extract_game_id function."""

    def test_valid_url(self) -> None:
        """Verify that a standard HLTB game URL yields the correct ID."""
        assert extract_game_id("https://howlongtobeat.com/game/12345") == "12345"

    def test_valid_url_trailing_slash(self) -> None:
        """Verify extraction works with a trailing slash."""
        assert extract_game_id("https://howlongtobeat.com/game/67890/") == "67890"

    @pytest.mark.parametrize(
        "url",
        [None, "", "https://example.com", "not-a-url"],
        ids=["none", "empty", "wrong_domain", "garbage"],
    )
    def test_invalid_url(self, url: str | None) -> None:
        """Verify that invalid URLs return None."""
        assert extract_game_id(url) is None


class TestValidateGame:
    """Tests for the validate_game function."""

    def test_valid_game(self) -> None:
        """Verify that a game dict with required fields passes validation."""
        game = {
            "game_id": 12345,
            "title": "The Legend of Zelda",
            "main_story_hours": 50.0,
        }
        assert validate_game(game) is True

    def test_missing_id(self) -> None:
        """Verify that a game dict missing game_id fails validation."""
        game = {"title": "Some Game"}
        assert validate_game(game) is False

    def test_missing_title(self) -> None:
        """Verify that a game dict missing title fails validation."""
        game = {"game_id": 123}
        assert validate_game(game) is False

    def test_empty_dict(self) -> None:
        """Verify that an empty dict fails validation."""
        assert validate_game({}) is False

    def test_none_values(self) -> None:
        """Verify that None values for required fields fail validation."""
        assert validate_game({"game_id": None, "title": None}) is False
