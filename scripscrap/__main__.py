"""CLI entrypoint: scrape public HTML tables and print them to stdout."""

from __future__ import annotations

import argparse
import sys

from scripscrap.output import write_csv, write_json
from scripscrap.scraper import ScrapeError, scrape_tables


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripscrap",
        description=(
            "Load a public page in Chromium, extract HTML tables, "
            "and print them to stdout."
        ),
    )
    parser.add_argument("url", help="Public page URL that contains HTML tables")
    parser.add_argument(
        "--format",
        choices=("csv", "json"),
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--table",
        type=int,
        metavar="N",
        default=None,
        help="0-based index of a single table to print (default: all tables)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Seconds to wait for navigation and table render (default: 30)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tables = scrape_tables(args.url, timeout=args.timeout)
        if args.format == "json":
            write_json(tables, table_index=args.table)
        else:
            write_csv(tables, table_index=args.table)
    except (ScrapeError, IndexError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
