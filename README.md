# scripscrap

Extract HTML tables from public JavaScript-rendered pages, from the CLI or a local web UI.

Use this only on **public pages** you are allowed to access. Do not collect personal information (PII). This tool does not log in, solve CAPTCHAs, or bypass access controls.

## Install

Python 3.11+ is required.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
playwright install chromium
```

On macOS/Linux, activate the venv with `source .venv/bin/activate`.

## Usage

```bash
python -m scripscrap https://example.com/page-with-tables
```

CSV is the default. Redirect stdout to save a file:

```bash
python -m scripscrap https://example.com/page-with-tables > tables.csv
```

JSON (object keyed by table index; `--table` prints that table as an array):

```bash
python -m scripscrap https://example.com/page-with-tables --format json
python -m scripscrap https://example.com/page-with-tables --format json --table 0
```

Options:

| Flag | Description |
| --- | --- |
| `--format csv\|json` | Output format (default: `csv`) |
| `--table N` | Print only the table at 0-based index `N` |
| `--timeout SECONDS` | Wait this long for navigation and a `table` to appear (default: `30`) |

When more than one table is printed as CSV, each table is preceded by a `# table N` comment line.

## How it works

1. Chromium (headless, via Playwright) loads the URL.
2. The scraper waits until a `table` element is in the DOM.
3. It reads `thead` headers and `tbody` rows. If there is no `thead`, the first row is used as headers.
4. Empty rows are skipped. Results go to stdout.

## Local web UI

A small Flask app on `127.0.0.1` lets you save named sources, scrape them, view the stored tables, and refresh when the remote page changes. Latest results are kept in `data/scripscrap.db`.

```bash
python -m scripscrap.web
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). Optional flags: `--host` and `--port`.

The first scrape for a source can take a while while Chromium loads the page. Failed refreshes keep the previous snapshot and show the error.
# scripscrap
