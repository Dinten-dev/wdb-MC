# ImmoScout24 Scraper

Selenium-based web scraper for collecting rental apartment listings from [immoscout24.ch](https://www.immoscout24.ch), focused on the Zurich housing market. Designed to collect **10,000+ listings** with structured data extraction, anti-detection measures, and reproducible analysis.

## Overview

The Zurich rental market is one of the most competitive in Switzerland. This project collects structured listing data to enable quantitative analysis of rental prices, apartment characteristics, and geographic distribution across ZIP codes.

**Technical approach:**
- Selenium WebDriver with headless Chrome for dynamic page rendering
- CSS selector fallback chains for robustness against layout changes
- Exponential backoff retry logic and user-agent rotation
- Automated ChromeDriver management via `webdriver-manager`

## Scraped Data Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `listing_id` | str | `"12345678"` | Unique ImmoScout24 listing ID |
| `url` | str | `"https://..."` | Direct link to the listing |
| `title` | str | `"3.5-Zi-Wohnung"` | Listing title |
| `price_chf` | float | `2450.0` | Monthly rent in CHF |
| `rooms` | float | `3.5` | Number of rooms |
| `area_m2` | float | `85.0` | Living area in m² |
| `price_per_m2` | float | `28.82` | Computed: price / area |
| `address` | str | `"Musterstr. 12"` | Full address |
| `zip_code` | str | `"8001"` | Swiss 4-digit postal code |
| `city` | str | `"Zürich"` | City name |
| `floor` | str | `"3. OG"` | Floor level |
| `available_from` | str | `"01.06.2026"` | Move-in date |
| `scraped_at` | str | `"2026-05-16T..."` | UTC timestamp of scraping |

## Quickstart

### Option 1: Docker (recommended)

```bash
docker compose up scraper
```

### Option 2: uv

```bash
pip install uv
uv pip install --system -e .
python -m scraper.scraper
```

### Option 3: pip

```bash
pip install -e .
python -m scraper.scraper
```

## EDA Notebook

```bash
docker compose up notebook
# Open http://localhost:8888 in your browser
```

Or run locally:

```bash
jupyter lab notebooks/eda.ipynb
```

## Tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=scraper --cov-report=term-missing
```

## Test Coverage

| Test | File | Input | Expected |
|------|------|-------|----------|
| `test_clean_price_valid` | `test_utils.py` | `"CHF 2'450.—"` | `2450.0` |
| `test_clean_price_returns_none` | `test_utils.py` | `None`, `""`, `"auf Anfrage"` | `None` |
| `test_clean_rooms_valid` | `test_utils.py` | `"3.5 Zimmer"` | `3.5` |
| `test_clean_rooms_none` | `test_utils.py` | `None`, `""` | `None` |
| `test_clean_area_valid` | `test_utils.py` | `"85 m²"` | `85.0` |
| `test_clean_area_none` | `test_utils.py` | `None` | `None` |
| `test_extract_zip_valid` | `test_utils.py` | `"..., 8001 Zürich"` | `"8001"` |
| `test_extract_zip_none` | `test_utils.py` | `None`, `"Zürich"` | `None` |
| `test_extract_listing_id_valid` | `test_utils.py` | URL with ID | `"12345678"` |
| `test_extract_listing_id_none` | `test_utils.py` | `None` | `None` |
| `test_validate_listing_valid` | `test_utils.py` | `{url, title}` | `True` |
| `test_validate_listing_missing_url` | `test_utils.py` | `{url: None}` | `False` |
| `test_validate_listing_empty_dict` | `test_utils.py` | `{}` | `False` |
| `test_scraper_default_values` | `test_scraper.py` | Default constructor | Correct defaults |
| `test_scraper_custom_params` | `test_scraper.py` | Custom params | Stored correctly |
| `test_accept_cookies_no_banner` | `test_scraper.py` | Mock driver | No exception |
| `test_extract_single_listing_invalid` | `test_scraper.py` | Empty mock element | `None` |
| `test_context_manager_quits_driver` | `test_scraper.py` | Mock driver | `quit()` called |

## EDA Key Findings

*Section populated after scraping run:*

1. Median monthly rent: `[X]` CHF
2. Room premium: each additional room adds ~`[X]`% to rent
3. Most expensive ZIP code: `[X]` with median `[X]` CHF/m²
4. Area-price correlation: r² = `[X]`
5. "Auf Anfrage" listings: `[X]`% of total

## Project Structure

```
immoscout-scraper/
├── scraper/
│   ├── __init__.py          # Package init
│   ├── config.py            # All constants, selectors, options
│   ├── utils.py             # Parsing, validation, logging helpers
│   └── scraper.py           # ImmoscoutScraper class
├── data/
│   └── .gitkeep             # Output directory for CSV and logs
├── notebooks/
│   └── eda.ipynb            # Exploratory data analysis
├── tests/
│   ├── __init__.py
│   ├── test_utils.py        # 13 unit tests for utils
│   └── test_scraper.py      # 5 integration tests with mocks
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions: ruff + pytest
├── Dockerfile               # Chromium + Python 3.11
├── docker-compose.yml       # Scraper + JupyterLab services
├── pyproject.toml            # Dependencies and tool config
├── .ruff.toml                # Linter rules
└── README.md
```

## Ethical Guidelines

- **robots.txt**: Checked at https://www.immoscout24.ch/robots.txt
- **Rate limiting**: Random delays (1.5–3.5s) between page requests to avoid overloading the server
- **No PII**: Only publicly visible listing data is collected; no personal contact information is stored
- **Public data only**: All scraped data is publicly accessible without authentication
- **Academic use**: This project is for educational and research purposes at FHNW

## License

MIT
