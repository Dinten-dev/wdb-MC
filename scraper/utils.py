"""Hilfsfunktionen für den ImmoScout24-Scraper.

Stellt Parsing-, Validierungs- und Logging-Funktionen bereit.
Alle Funktionen sind seiteneffektfrei (ausser ``setup_logging``)
und geben bei ungültigen Eingaben ``None`` statt Exceptions zurück.

Typical usage::

    from scraper.utils import clean_price, clean_rooms, setup_logging

    logger = setup_logging("data/scraper.log")
    price = clean_price("CHF 2'450.—")
"""

import logging
import re
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from scraper.config import LOG_DATE_FORMAT, LOG_FORMAT

# ---------------------------------------------------------------------------
# Kompilierte Regex-Muster (einmalig, nicht bei jedem Aufruf)
# ---------------------------------------------------------------------------
_PRICE_DIGITS_PATTERN: re.Pattern[str] = re.compile(r"[\d'.]+")
_AREA_NUMBER_PATTERN: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)?)")
_ZIP_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{4})\b")
_LISTING_ID_PATTERN: re.Pattern[str] = re.compile(r"(\d+)\s*$")
_ROOMS_NUMBER_PATTERN: re.Pattern[str] = re.compile(r"(\d+(?:[.,]\d+)?)")

_PRICE_NOISE_STRINGS: list[str] = [
    "auf anfrage",
    "preis auf anfrage",
]


def clean_price(raw: str | None) -> float | None:
    """Extrahiert einen numerischen Mietpreis aus einem Roh-String.

    Erkennt gängige ImmoScout24-Preisformate wie ``CHF 2'450.—``,
    ``ab CHF 1'800/Mt.`` oder ``CHF 3.500`` und normalisiert sie
    zu einem ``float``-Wert.

    Args:
        raw: Roh-Preisstring aus dem DOM, z.B. ``"CHF 2'450.—"``.
            Darf ``None`` oder ein leerer String sein.

    Returns:
        Den bereinigten Preis als ``float``, oder ``None`` wenn der
        String nicht parsbar ist (z.B. ``"auf Anfrage"``).

    Examples:
        >>> clean_price("CHF 2'450.—")
        2450.0
        >>> clean_price("Preis auf Anfrage")
        >>> clean_price(None)
    """
    if not raw or not raw.strip():
        return None

    lower = raw.strip().lower()

    if lower in _PRICE_NOISE_STRINGS:
        return None

    # Präfix und Suffix entfernen
    cleaned = raw.replace("CHF", "").replace("chf", "")
    cleaned = cleaned.replace("/Mt.", "").replace("/mt.", "")
    cleaned = cleaned.replace("—", "").replace("–", "").replace("-", "")
    cleaned = cleaned.replace("ab", "").replace("ca.", "")
    cleaned = cleaned.strip()

    match = _PRICE_DIGITS_PATTERN.search(cleaned)
    if not match:
        return None

    number_str = match.group(0)

    # Apostrophe als Tausender-Trenner entfernen
    number_str = number_str.replace("'", "")

    # Punkt als Tausender-Trenner erkennen: "3.500" → 3500
    # Punkt ist nur ein Dezimaltrenner wenn danach 1-2 Ziffern folgen
    parts = number_str.split(".")
    if len(parts) == 2 and len(parts[1]) == 3:
        # "3.500" → Tausender-Trenner, nicht Dezimal
        number_str = number_str.replace(".", "")

    try:
        return float(number_str)
    except ValueError:
        return None


def clean_rooms(raw: str | None) -> float | None:
    """Extrahiert die Zimmeranzahl aus einem Roh-String.

    Unterstützt Formate wie ``"3.5 Zimmer"``, ``"3,5 Zi."``
    oder einfach ``"4"``. Komma wird zu Punkt normalisiert.

    Args:
        raw: Roh-Zimmerstring aus dem DOM, z.B. ``"3.5 Zimmer"``.
            Darf ``None`` oder ein leerer String sein.

    Returns:
        Die Zimmeranzahl als ``float``, oder ``None`` wenn
        der String nicht parsbar ist.

    Examples:
        >>> clean_rooms("3.5 Zimmer")
        3.5
        >>> clean_rooms("4")
        4.0
        >>> clean_rooms(None)
    """
    if not raw or not raw.strip():
        return None

    normalized = raw.strip().replace(",", ".")

    match = _ROOMS_NUMBER_PATTERN.search(normalized)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def clean_area(raw: str | None) -> float | None:
    """Extrahiert die Wohnfläche in m² aus einem Roh-String.

    Erkennt Formate wie ``"85 m²"``, ``"85.0 m²"``, ``"85m2"``
    oder ``"ca. 85 m²"`` und gibt den numerischen Wert zurück.

    Args:
        raw: Roh-Flächenstring aus dem DOM, z.B. ``"85 m²"``.
            Darf ``None`` oder ein leerer String sein.

    Returns:
        Die Fläche als ``float`` in m², oder ``None`` wenn
        der String nicht parsbar ist.

    Examples:
        >>> clean_area("85 m²")
        85.0
        >>> clean_area("ca. 85 m²")
        85.0
        >>> clean_area(None)
    """
    if not raw or not raw.strip():
        return None

    match = _AREA_NUMBER_PATTERN.search(raw.strip())
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_zip(address: str | None) -> str | None:
    """Extrahiert eine Schweizer Postleitzahl (4 Ziffern) aus einer Adresse.

    Sucht das erste Vorkommen einer 4-stelligen Zahl an einer
    Wortgrenze im Adress-String.

    Args:
        address: Vollständiger Adress-String, z.B.
            ``"Musterstrasse 12, 8001 Zürich"``.
            Darf ``None`` oder ein leerer String sein.

    Returns:
        Die PLZ als ``str`` (z.B. ``"8001"``), oder ``None``
        wenn keine 4-stellige Zahl gefunden wird.

    Examples:
        >>> extract_zip("Musterstrasse 12, 8001 Zürich")
        '8001'
        >>> extract_zip("Zürich")
    """
    if not address or not address.strip():
        return None

    match = _ZIP_PATTERN.search(address)
    if not match:
        return None

    return match.group(1)


def extract_listing_id(url: str | None) -> str | None:
    """Extrahiert die Inserats-ID aus einer ImmoScout24-URL.

    Die ID ist die letzte Ziffernfolge am Ende der URL, z.B.
    ``/d/3-zimmer-wohnung-12345678`` → ``"12345678"``.

    Args:
        url: Vollständige Inserat-URL, z.B.
            ``"https://www.immoscout24.ch/de/d/wohnung-12345678"``.
            Darf ``None`` oder ein leerer String sein.

    Returns:
        Die Inserats-ID als ``str``, oder ``None`` wenn keine
        Ziffernfolge am URL-Ende gefunden wird.

    Examples:
        >>> extract_listing_id("https://immoscout24.ch/de/d/wohnung-12345678")
        '12345678'
        >>> extract_listing_id(None)
    """
    if not url or not url.strip():
        return None

    # Query-Parameter und Fragmente entfernen
    clean_url = url.split("?")[0].split("#")[0].rstrip("/")

    match = _LISTING_ID_PATTERN.search(clean_url)
    if not match:
        return None

    return match.group(1)


def validate_listing(listing: dict) -> bool:
    """Prüft ob ein Listing-Dictionary die Pflichtfelder enthält.

    Ein Listing ist gültig wenn mindestens ``url`` und ``title``
    als non-None-Werte vorhanden sind. Alle anderen Felder
    dürfen ``None`` sein.

    Args:
        listing: Dictionary mit Listing-Daten, z.B.
            ``{"url": "https://...", "title": "3.5-Zi-Wohnung", ...}``.

    Returns:
        ``True`` wenn ``url`` und ``title`` vorhanden und nicht
        ``None`` sind, sonst ``False``.

    Examples:
        >>> validate_listing({"url": "https://...", "title": "Wohnung"})
        True
        >>> validate_listing({"url": None, "title": "Wohnung"})
        False
    """
    required_fields: list[str] = ["url", "title"]
    return all(listing.get(field) is not None for field in required_fields)


def try_extract(
    driver: WebDriver | WebElement,
    selectors: list[str],
    attribute: str = "text",
) -> str | None:
    """Versucht einen Wert über eine Fallback-Liste von CSS-Selektoren zu extrahieren.

    Iteriert über die ``selectors``-Liste und gibt den Wert des
    ersten erfolgreichen Selektors zurück. Schlägt kein Selektor
    an, wird ``None`` zurückgegeben (kein Exception-Raising).

    Args:
        driver: Aktive Selenium-WebDriver- oder WebElement-Instanz.
        selectors: Liste von CSS-Selektoren, die der Reihe nach
            probiert werden (erstes Match gewinnt).
        attribute: Art des zu extrahierenden Werts.
            ``"text"`` für ``.text`` / ``textContent``,
            ``"href"`` für ``.get_attribute("href")``,
            oder ein beliebiges HTML-Attribut.

    Returns:
        Den extrahierten String-Wert, oder ``None`` wenn
        kein Selektor ein Element findet.

    Examples:
        >>> value = try_extract(driver, ["[data-test='price']", ".price"], "text")
    """
    for selector in selectors:
        try:
            element = driver.find_element("css selector", selector)
        except NoSuchElementException:
            continue

        if attribute == "text":
            text = element.text
            if text and text.strip():
                return text.strip()
            # Fallback: textContent für versteckte Elemente
            text_content = element.get_attribute("textContent")
            if text_content and text_content.strip():
                return text_content.strip()
        else:
            attr_value = element.get_attribute(attribute)
            if attr_value and attr_value.strip():
                return attr_value.strip()

    return None


def setup_logging(
    log_file: str,
    level: int = logging.INFO,
) -> logging.Logger:
    """Konfiguriert den Root-Logger mit Stream- und File-Handler.

    Erstellt einen Logger mit dem Namen ``immoscout-scraper``,
    einem ``StreamHandler`` (auf ``level``) und einem
    ``FileHandler`` (auf ``DEBUG``). Verhindert doppelte Handler
    bei wiederholtem Aufruf.

    Args:
        log_file: Pfad zur Log-Datei, z.B. ``"data/scraper.log"``.
            Übergeordnete Verzeichnisse werden automatisch erstellt.
        level: Log-Level für den StreamHandler (Console).
            Standard: ``logging.INFO``.

    Returns:
        Konfigurierte ``logging.Logger``-Instanz.

    Examples:
        >>> logger = setup_logging("data/scraper.log")
        >>> logger.info("Scraper gestartet")
    """
    logger_name = "immoscout-scraper"
    logger = logging.getLogger(logger_name)

    # Doppelte Handler verhindern bei wiederholtem Aufruf
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console-Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File-Handler (erstellt Verzeichnisse bei Bedarf)
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
