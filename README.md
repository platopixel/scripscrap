# scripscrap

Extract HTML tables from public JavaScript-rendered pages, from the CLI or a local web UI. The web app can also POST a new matchup to a remote add-matchup endpoint, and browse or edit weekly duels on the Weeks page.

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

Keep the venv activated in any later terminal session (`source .venv/bin/activate`). The install puts `scripscrap` and `scripscrap-web` on that venv’s PATH.

## Run the web app

From the repository root, with the venv active:

```bash
source .venv/bin/activate
python -m scripscrap.web
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Leave that terminal running; stop the server with Ctrl+C.

`python -m scripscrap.web` is the reliable way to start the UI. After a successful `pip install -e .`, `scripscrap-web` does the same thing, but only if the venv is active — otherwise the shell reports `command not found`.

Optional flags: `--host` (default `127.0.0.1`) and `--port` (default `5000`). Example: `python -m scripscrap.web --port 8000`.

Optional env vars (export them in the same terminal **before** starting the server). None of these are required for scraping tables.

```bash
export ADD_MATCHUP_TOKEN="your-token"
export SLATE_API_URL="https://slate-api.example"
export SLATE_API_TOKEN="your-slate-token"
python -m scripscrap.web
```

On Windows (cmd): `set ADD_MATCHUP_TOKEN=your-token`, `set SLATE_API_URL=https://slate-api.example`, and `set SLATE_API_TOKEN=your-slate-token`.

- `ADD_MATCHUP_TOKEN` — optional Bearer token for the home-page **Post matchup** form (add-matchup Cloud Run). If set, it is sent as `Authorization: Bearer …`.
- `SLATE_API_URL` — required for the **Weeks** page (`/weeks`). Base URL with no trailing slash.
- `SLATE_API_TOKEN` — optional Bearer token for the Weeks slate API. If set, it is sent as `Authorization: Bearer …`.

If `SLATE_API_URL` is unset, `/weeks` still loads and shows how to configure it. That empty state is supported.

The slate API contract and sample payloads are in [`docs/weekly-duel-editor.md`](docs/weekly-duel-editor.md) and [`docs/fixtures/`](docs/fixtures/).

From the home page you can:

- Save a named public URL, scrape its HTML tables, and keep the latest snapshot in SQLite (`data/scripscrap.db`, created automatically and gitignored)
- Open a source to view stored tables, refresh, export CSV/JSON, or delete it
- Fill in a matchup (week, lock/freeze times, two players) and POST it to the add-matchup endpoint (create a duel)
- Open **Weeks** in the header (`/weeks`) to browse and edit duels for a slate week. That is separate from **Post matchup** on the home page.

The first scrape for a source can take a while while Chromium loads the page. Failed refreshes keep the previous snapshot and show the error.

## CLI

Scrape a public page and print tables to stdout. CSV is the default:

```bash
source .venv/bin/activate
python -m scripscrap https://example.com/page-with-tables
python -m scripscrap https://example.com/page-with-tables > tables.csv
```

JSON (object keyed by table index; `--table` prints that table as an array):

```bash
python -m scripscrap https://example.com/page-with-tables --format json
python -m scripscrap https://example.com/page-with-tables --format json --table 0
```

`scripscrap` is the same as `python -m scripscrap` when the venv is active.

| Flag | Description |
| --- | --- |
| `--format csv\|json` | Output format (default: `csv`) |
| `--table N` | Print only the table at 0-based index `N` |
| `--timeout SECONDS` | Wait this long for navigation and a `table` to appear (default: `30`) |

When more than one table is printed as CSV, each table is preceded by a `# table N` comment line.

## How scraping works

1. Chromium (headless, via Playwright) loads the URL.
2. The scraper waits until a `table` element is in the DOM.
3. It reads `thead` headers and `tbody` rows. If there is no `thead`, the first row is used as headers.
4. Empty rows are skipped. The CLI writes results to stdout; the web UI stores the latest snapshot in `data/scripscrap.db`.
