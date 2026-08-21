"""Load a public page with Playwright and extract HTML tables."""

from __future__ import annotations

from dataclasses import dataclass, field

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (compatible; Scripscrap/0.1; +https://github.com/scripscrap) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TABLE_JS = """
() => {
  const clean = (el) => (el?.innerText || "").replace(/\\s+/g, " ").trim();

  const cellsFrom = (row, selector) =>
    Array.from(row.querySelectorAll(selector)).map(clean);

  return Array.from(document.querySelectorAll("table")).map((table) => {
    const headerCells = Array.from(table.querySelectorAll("thead th, thead td"));
    let headers = headerCells.map(clean);

    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const allRows = Array.from(table.querySelectorAll("tr"));
    const dataRows = bodyRows.length ? bodyRows : allRows;

    const rows = [];
    for (const row of dataRows) {
      if (row.closest("thead")) continue;
      const cells = cellsFrom(row, "td, th");
      if (!cells.length || cells.every((c) => !c)) continue;
      rows.push(cells);
    }

    if (!headers.length && rows.length) {
      headers = rows.shift();
    }

    return { headers, rows };
  });
}
"""


@dataclass
class Table:
    """A parsed HTML table with header names and data rows."""

    headers: list[str]
    rows: list[list[str]] = field(default_factory=list)

    def as_dicts(self) -> list[dict[str, str]]:
        headers = self.unique_headers()
        width = len(headers)
        records: list[dict[str, str]] = []
        for row in self.rows:
            padded = (row + [""] * width)[:width]
            records.append(dict(zip(headers, padded)))
        return records

    def unique_headers(self) -> list[str]:
        if not self.headers:
            width = max((len(r) for r in self.rows), default=0)
            return [f"column_{i + 1}" for i in range(width)]

        seen: dict[str, int] = {}
        unique: list[str] = []
        for raw in self.headers:
            name = raw or "column"
            count = seen.get(name, 0)
            seen[name] = count + 1
            unique.append(name if count == 0 else f"{name}_{count + 1}")
        return unique


def select_tables(
    tables: list[Table], table_index: int | None
) -> list[tuple[int, Table]]:
    """Return (index, table) pairs, or a single table when *table_index* is set."""
    items = list(enumerate(tables))
    if table_index is None:
        return items
    if table_index < 0 or table_index >= len(items):
        raise IndexError(
            f"Table index {table_index} is out of range (found {len(items)} table(s))"
        )
    return [items[table_index]]


class ScrapeError(RuntimeError):
    """Raised when the page cannot be loaded or no tables are found."""


def scrape_tables(url: str, timeout: float = 30.0) -> list[Table]:
    """Open *url* in Chromium, wait for a table, and return parsed tables."""
    timeout_ms = int(timeout * 1000)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_selector("table", timeout=timeout_ms)
                raw_tables = page.evaluate(TABLE_JS)
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise ScrapeError(
            f"Timed out after {timeout:g}s waiting for a table on {url}"
        ) from exc
    except Exception as exc:
        raise ScrapeError(f"Failed to load {url}: {exc}") from exc

    tables = [
        Table(headers=item.get("headers") or [], rows=item.get("rows") or [])
        for item in raw_tables
        if item.get("headers") or item.get("rows")
    ]
    if not tables:
        raise ScrapeError(f"No HTML tables found on {url}")
    return tables
