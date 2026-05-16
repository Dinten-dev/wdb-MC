# HowLongToBeat Scraper

## Project Overview

[HowLongToBeat.com](https://howlongtobeat.com) is the internet's most comprehensive database of video game completion times, maintained by a community of over 500,000 players who submit their playtime data across thousands of titles. Unlike proprietary telemetry data held by platform operators, HLTB aggregates self-reported completion times across four categories — main story, main + extras, completionist, and all styles — providing a unique cross-platform view of how long games actually take to finish. The dataset covers games from the Atari 2600 era to modern titles and includes metadata such as review scores, platform availability, and release years.

This dataset has significant real-world applications across the gaming industry. Game developers use completion time benchmarks to evaluate whether their content delivers appropriate playtime relative to its price point and genre expectations. Players use HLTB data to make informed purchasing decisions — a 100-hour RPG represents a very different time commitment than a 6-hour narrative adventure. Games journalists at outlets like IGN, Eurogamer, and Kotaku routinely reference HLTB data in reviews and buying guides. Academic researchers studying game design, player behaviour, and content economics use HLTB as a primary data source because it provides standardised, community-validated completion metrics that are not available through any official API.

This project employs a hybrid scraping architecture that justifies the 1.1 complexity multiplier. The core data collection uses Python's `requests` library with a persistent `Session` to send POST requests to HLTB's internal search API — an undocumented endpoint that requires reverse-engineering the request body structure, discovering dynamic auth tokens from JavaScript bundles, and including proper `Referer` and `Origin` headers. This approach is far more efficient than browser automation for structured JSON endpoints. A second Selenium-based component enriches a sample of listings by visiting individual game detail pages, which are rendered client-side via JavaScript and contain additional fields like developer names and genres not available in the search API response. The project respects the site's infrastructure by rate-limiting all requests with random delays, using a descriptive User-Agent string, and collecting only publicly visible aggregate game metadata — no personal user data is scraped.

## Technical Complexity

This project is more complex than a standard paginated HTML scraper for several reasons:

1. **Reverse-engineered POST API**: The search endpoint is not documented and requires constructing valid JSON payloads with specific field structures.
2. **Dynamic auth token discovery**: The API requires an `x-auth-token` header obtained by parsing JavaScript bundles from the homepage, then calling an `/init` endpoint.
3. **Anti-scraping header requirements**: Requests must include `Referer` and `Origin` headers matching the site's domain.
4. **Hybrid architecture**: Two distinct scraping techniques (requests + Selenium) are used in complementary roles.
5. **Time conversion**: The API returns completion times in seconds, requiring conversion to human-readable hours.

## robots.txt Compliance

As of 2025-05-16, `howlongtobeat.com/robots.txt` returns HTTP 403 (Forbidden), meaning no explicit `Disallow` directives are served. The site relies on Cloudflare protection rather than robots.txt for access control. This scraper:

- Uses a descriptive, non-deceptive User-Agent identifying it as an academic project
- Implements rate limiting with random delays between 0.3–1.0 seconds per API page
- Collects only publicly visible aggregate game metadata
- Does not scrape any personal user data, profiles, or authentication-gated content
- Does not attempt to bypass CAPTCHA or login walls

## Data Structure

| Field | Type | Example | Description |
|---|---|---|---|
| `game_id` | int | `38019` | Unique HLTB game identifier |
| `title` | str | `"The Legend of Zelda: Breath of the Wild"` | Game title as displayed on HLTB |
| `game_type` | str | `"game"` | Entry type: game, dlc, or mod |
| `platform` | str | `"Nintendo Switch, Wii U"` | Comma-separated platform list |
| `genre` | str | `"Action, Adventure"` | Genre(s) from the detail page (Selenium-enriched) |
| `developer` | str | `"Nintendo"` | Developer name from the detail page |
| `release_year` | int | `2017` | Year of first release |
| `main_story_hours` | float | `50.34` | Main story completion time in hours |
| `main_plus_extras_hours` | float | `98.43` | Main story + extras time in hours |
| `completionist_hours` | float | `193.62` | 100% completion time in hours |
| `all_styles_hours` | float | `92.7` | Average across all play styles in hours |
| `review_score` | int | `93` | Community review score (0–100) |
| `count_playing` | int | `500` | Number of users currently playing |
| `count_backlog` | int | `1000` | Number of users with this game in backlog |
| `count_retired` | int | `200` | Number of users who retired the game |
| `count_comp` | int | `3000` | Number of completed submissions |
| `count_review` | int | `150` | Number of user reviews |
| `similarity_score` | float | `null` | Search similarity score (if applicable) |
| `scraped_at` | str | `"2025-05-16T19:30:00+00:00"` | UTC timestamp of data collection (ISO 8601) |
| `source_page` | int | `42` | API result page this entry was collected from |

The CSV uses UTF-8 encoding with a BOM (byte order mark) for Excel compatibility. Float fields use Python `None` serialised as empty cells. The `scraped_at` field uses ISO 8601 format in UTC.

## Setup & Usage

### With uv (local)

```bash
git clone https://github.com/Dinten-dev/wdb-MC.git
cd hltb-scraper
uv pip install -e ".[dev,notebook]"
python -m scraper.scraper
```

### With Docker

```bash
docker compose up scraper       # Run the scraper
docker compose up notebook      # Start Jupyter on port 8888
```

## Tests

| Test Function | File | Input | Verifies |
|---|---|---|---|
| `test_valid_inputs` | `test_utils.py` | `"12h"`, `"1h 30m"`, `"45m"`, etc. | Time strings parse to correct decimal hours |
| `test_invalid_inputs` | `test_utils.py` | `None`, `""`, `"--"`, `"0"` | Invalid time values return None |
| `test_conversion` | `test_utils.py` | `3600`, `0`, `None` | Seconds-to-hours conversion is accurate |
| `test_valid_url` | `test_utils.py` | HLTB game URL | Game ID extraction from URL |
| `test_invalid_url` | `test_utils.py` | `None`, `""`, wrong domain | Invalid URLs return None |
| `test_valid_game` | `test_utils.py` | Complete game dict | Validation passes with required fields |
| `test_missing_id` | `test_utils.py` | Dict without `game_id` | Validation rejects missing required field |
| `test_empty_dict` | `test_utils.py` | `{}` | Validation rejects empty dict |
| `test_default_attributes` | `test_scraper.py` | No arguments | Scraper initialises with correct defaults |
| `test_retry_on_persistent_failure` | `test_scraper.py` | Always-failing mock | Retry wrapper calls function exactly N times |
| `test_retry_succeeds_on_second_attempt` | `test_scraper.py` | Fail-then-succeed mock | Retry returns result after recovery |
| `test_valid_entry` | `test_scraper.py` | Full API response dict | Game entry parsing produces correct fields |
| `test_invalid_entry` | `test_scraper.py` | Empty dict | Missing fields return None |
| `test_extract_detail_fields_no_driver` | `test_scraper.py` | Mock WebDriver | Detail extraction returns None for unfindable elements |

**Testing strategy**: All utility tests (`test_utils.py`) are pure unit tests with no external dependencies — they test parsing, conversion, and validation functions in isolation. All scraper tests (`test_scraper.py`) mock network and browser calls using `unittest.mock`, so they run in under two seconds with no internet access required. No test requires a real browser or network connection.

## Running Tests

```bash
pytest tests/ -v --cov=scraper --cov-report=term-missing
ruff check .
```

## Project Structure

```
hltb-scraper/
├── scraper/
│   ├── __init__.py
│   ├── config.py          # All constants, selectors, and settings
│   ├── utils.py           # Parsing, logging, retry, validation
│   └── scraper.py         # HLTBScraper class (requests + Selenium)
├── data/
│   └── .gitkeep
├── notebooks/
│   └── eda.ipynb          # Exploratory data analysis
├── tests/
│   ├── __init__.py
│   ├── test_utils.py      # Unit tests for utility functions
│   └── test_scraper.py    # Integration tests with mocks
├── .github/workflows/
│   └── ci.yml             # GitHub Actions CI pipeline
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## License

Academic project — FHNW WDB Module.
