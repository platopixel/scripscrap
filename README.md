# scripscrap

Extract HTML tables from public JavaScript-rendered pages, from the CLI or a local web UI. The web app can also POST a player matchup payload to a remote add-matchup endpoint.

Use this only on **public pages** you are allowed to access. Do not collect personal information (PII). This tool does not log in, solve CAPTCHAs, or bypass access controls.

## Requirements

- Python 3.11 or newer
- Chromium for Playwright (installed in the next section)

## Install

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

On Windows, activate the venv with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

That install provides two commands: `scripscrap` (CLI) and `scripscrap-web` (local UI). You can also run the same entry points as `python -m scripscrap` and `python -m scripscrap.web`.

## Environment

The matchup form in the web UI POSTs to the add-matchup Cloud Run service. If that service requires a bearer token, export it before starting the UI:

```bash
export ADD_MATCHUP_TOKEN="your-token"
```

On Windows (cmd): `set ADD_MATCHUP_TOKEN=your-token`.

The token is optional in code: if it is set, it is sent as `Authorization: Bearer …`. Scraping tables does not need this variable.

Latest scrape results for the web UI are stored in `data/scripscrap.db` (created automatically). That directory is gitignored.

## Run locally

### CLI

Scrape a public page and print tables to stdout. CSV is the default:

```bash
scripscrap https://example.com/page-with-tables
scripscrap https://example.com/page-with-tables > tables.csv
```

JSON (object keyed by table index; `--table` prints that table as an array):

```bash
scripscrap https://example.com/page-with-tables --format json
scripscrap https://example.com/page-with-tables --format json --table 0
```

| Flag | Description |
| --- | --- |
| `--format csv\|json` | Output format (default: `csv`) |
| `--table N` | Print only the table at 0-based index `N` |
| `--timeout SECONDS` | Wait this long for navigation and a `table` to appear (default: `30`) |

When more than one table is printed as CSV, each table is preceded by a `# table N` comment line.

### Web UI

```bash
scripscrap-web
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). Optional flags: `--host` and `--port`.

From the home page you can:

- Save a named public URL, scrape its HTML tables, and keep the latest snapshot in SQLite
- Open a source to view stored tables, refresh, export CSV/JSON, or delete it
- Fill in a matchup (week, lock/freeze times, two players) and POST it to the add-matchup endpoint

The first scrape for a source can take a while while Chromium loads the page. Failed refreshes keep the previous snapshot and show the error.

## How scraping works

1. Chromium (headless, via Playwright) loads the URL.
2. The scraper waits until a `table` element is in the DOM.
3. It reads `thead` headers and `tbody` rows. If there is no `thead`, the first row is used as headers.
4. Empty rows are skipped. The CLI writes results to stdout; the web UI stores the latest snapshot in `data/scripscrap.db`.
