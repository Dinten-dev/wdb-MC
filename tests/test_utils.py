"""Unit tests for scraper.utils parsing and validation functions."""

import pytest

from scraper.utils import (
    clean_area,
    clean_price,
    clean_rooms,
    extract_listing_id,
    extract_zip,
    validate_listing,
)


class TestCleanPrice:
    """Tests for the clean_price function."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("CHF 2'450.—", 2450.0),
            ("ab CHF 1'800/Mt.", 1800.0),
            ("CHF 3.500", 3500.0),
            ("2450", 2450.0),
            ("1'200", 1200.0),
        ],
    )
    def test_clean_price_valid(self, raw: str, expected: float) -> None:
        """Verify that valid price strings are parsed correctly.

        Args:
            raw: Input price string.
            expected: Expected parsed float value.
        """
        assert clean_price(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, "", "   ", "auf Anfrage", "Preis auf Anfrage"],
    )
    def test_clean_price_returns_none(self, raw: str | None) -> None:
        """Verify that unparseable or empty inputs return None.

        Args:
            raw: Input that should yield None.
        """
        assert clean_price(raw) is None


class TestCleanRooms:
    """Tests for the clean_rooms function."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("3.5 Zimmer", 3.5),
            ("3,5 Zi.", 3.5),
            ("4", 4.0),
            ("4.5", 4.5),
        ],
    )
    def test_clean_rooms_valid(self, raw: str, expected: float) -> None:
        """Verify that valid room strings are parsed correctly.

        Args:
            raw: Input room string.
            expected: Expected parsed float value.
        """
        assert clean_rooms(raw) == expected

    @pytest.mark.parametrize("raw", [None, ""])
    def test_clean_rooms_none(self, raw: str | None) -> None:
        """Verify that None and empty string return None.

        Args:
            raw: Input that should yield None.
        """
        assert clean_rooms(raw) is None


class TestCleanArea:
    """Tests for the clean_area function."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("85 m²", 85.0),
            ("ca. 85 m²", 85.0),
            ("85.5 m²", 85.5),
            ("120m2", 120.0),
        ],
    )
    def test_clean_area_valid(self, raw: str, expected: float) -> None:
        """Verify that valid area strings are parsed correctly.

        Args:
            raw: Input area string.
            expected: Expected parsed float value.
        """
        assert clean_area(raw) == expected

    def test_clean_area_none(self) -> None:
        """Verify that None returns None."""
        assert clean_area(None) is None


class TestExtractZip:
    """Tests for the extract_zip function."""

    @pytest.mark.parametrize(
        ("address", "expected"),
        [
            ("Musterstrasse 12, 8001 Zürich", "8001"),
            ("8050 Zürich-Oerlikon", "8050"),
            ("Bahnhofstrasse 1, CH-8001 Zürich", "8001"),
        ],
    )
    def test_extract_zip_valid(
        self, address: str, expected: str
    ) -> None:
        """Verify that Swiss ZIP codes are extracted correctly.

        Args:
            address: Input address string.
            expected: Expected 4-digit ZIP code.
        """
        assert extract_zip(address) == expected

    @pytest.mark.parametrize("address", [None, "Zürich"])
    def test_extract_zip_none(self, address: str | None) -> None:
        """Verify that None and ZIP-less strings return None.

        Args:
            address: Input that should yield None.
        """
        assert extract_zip(address) is None


class TestExtractListingId:
    """Tests for the extract_listing_id function."""

    def test_extract_listing_id_valid(self) -> None:
        """Verify that the trailing numeric ID is extracted from a URL."""
        url = "https://www.immoscout24.ch/de/d/3-zimmer-wohnung-zuerich-12345678"
        assert extract_listing_id(url) == "12345678"

    def test_extract_listing_id_none(self) -> None:
        """Verify that None input returns None."""
        assert extract_listing_id(None) is None


class TestValidateListing:
    """Tests for the validate_listing function."""

    def test_validate_listing_valid(self) -> None:
        """Verify that a listing with url and title passes validation."""
        listing = {"url": "https://example.com", "title": "Wohnung"}
        assert validate_listing(listing) is True

    def test_validate_listing_missing_url(self) -> None:
        """Verify that a listing with None url fails validation."""
        listing = {"url": None, "title": "Wohnung"}
        assert validate_listing(listing) is False

    def test_validate_listing_empty_dict(self) -> None:
        """Verify that an empty dict fails validation."""
        assert validate_listing({}) is False
