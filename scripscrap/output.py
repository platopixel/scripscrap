"""Write extracted tables as CSV or JSON."""

from __future__ import annotations

import csv
import json
import sys
from typing import Iterable, TextIO

from scripscrap.scraper import Table, select_tables


def write_csv(
    tables: Iterable[Table],
    *,
    table_index: int | None = None,
    file: TextIO | None = None,
) -> None:
    out = file or sys.stdout
    selected = select_tables(list(tables), table_index)
    writer = csv.writer(out, lineterminator="\n")
    multiple = len(selected) > 1
    for i, (index, table) in enumerate(selected):
        if multiple:
            if i:
                print(file=out)
            print(f"# table {index}", file=out)
        headers = table.unique_headers()
        writer.writerow(headers)
        width = len(headers)
        for row in table.rows:
            writer.writerow((row + [""] * width)[:width])


def write_json(
    tables: Iterable[Table],
    *,
    table_index: int | None = None,
    file: TextIO | None = None,
) -> None:
    out = file or sys.stdout
    selected = select_tables(list(tables), table_index)
    payload = {str(index): table.as_dicts() for index, table in selected}
    if table_index is not None:
        json.dump(payload[str(table_index)], out, indent=2)
    else:
        json.dump(payload, out, indent=2)
    print(file=out)
