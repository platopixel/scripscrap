"""Local Flask UI for saving sources and refreshing scraped tables."""

from __future__ import annotations

import argparse
import json
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from scripscrap.matchup import EXAMPLE_MATCHUP, MatchupError, post_matchup
from scripscrap.output import write_csv, write_json
from scripscrap.scraper import ScrapeError, Table, scrape_tables, select_tables
from scripscrap.store import Store

HERE = Path(__file__).resolve().parent


def create_app(store: Store | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(HERE / "templates"),
        static_folder=str(HERE / "static"),
    )
    app.secret_key = "scripscrap-local"
    app.config["STORE"] = store or Store()

    @app.get("/")
    def index():
        sources = app.config["STORE"].list_sources()
        return render_template(
            "index.html",
            sources=sources,
            example_payload=json.dumps(EXAMPLE_MATCHUP, indent=2),
        )

    @app.post("/sources")
    def create_source():
        store: Store = app.config["STORE"]
        parsed = _form_source(request.form)
        if parsed is None:
            return redirect(url_for("index"))
        source_id = store.add_source(**parsed)
        _run_scrape(store, source_id)
        return redirect(url_for("show_source", source_id=source_id))

    @app.get("/sources/<int:source_id>")
    def show_source(source_id: int):
        store: Store = app.config["STORE"]
        source = store.get_source(source_id)
        if source is None:
            flash("Source not found.", "error")
            return redirect(url_for("index"))
        snapshot = store.get_snapshot(source_id)
        return render_template("source.html", source=source, snapshot=snapshot)

    @app.post("/sources/<int:source_id>")
    def update_source(source_id: int):
        store: Store = app.config["STORE"]
        if store.get_source(source_id) is None:
            flash("Source not found.", "error")
            return redirect(url_for("index"))
        parsed = _form_source(request.form)
        if parsed is None:
            return redirect(url_for("show_source", source_id=source_id))
        store.update_source(source_id, **parsed)
        flash("Source settings saved.", "ok")
        return redirect(url_for("show_source", source_id=source_id))

    @app.post("/sources/<int:source_id>/refresh")
    def refresh_source(source_id: int):
        store: Store = app.config["STORE"]
        if store.get_source(source_id) is None:
            flash("Source not found.", "error")
            return redirect(url_for("index"))
        _run_scrape(store, source_id)
        return redirect(url_for("show_source", source_id=source_id))

    @app.post("/sources/<int:source_id>/delete")
    def delete_source(source_id: int):
        store: Store = app.config["STORE"]
        store.delete_source(source_id)
        flash("Source deleted.", "ok")
        return redirect(url_for("index"))

    @app.get("/sources/<int:source_id>/export.csv")
    def export_csv(source_id: int):
        tables = _tables_for_export(app.config["STORE"], source_id)
        if tables is None:
            return redirect(url_for("index"))
        buf = StringIO()
        write_csv(tables, file=buf)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=source-{source_id}.csv"
            },
        )

    @app.get("/sources/<int:source_id>/export.json")
    def export_json(source_id: int):
        tables = _tables_for_export(app.config["STORE"], source_id)
        if tables is None:
            return redirect(url_for("index"))
        buf = StringIO()
        write_json(tables, file=buf)
        return Response(
            buf.getvalue(),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=source-{source_id}.json"
            },
        )

    @app.post("/matchups")
    def send_matchup():
        payload = _matchup_payload_from_request()
        if payload is None:
            return redirect(request.referrer or url_for("index"))
        try:
            result = post_matchup(payload)
        except MatchupError as exc:
            flash(str(exc), "error")
            return redirect(request.referrer or url_for("index"))
        preview = result.text.strip() or "(empty body)"
        if len(preview) > 240:
            preview = preview[:237] + "..."
        if result.ok:
            flash(f"Matchup posted ({result.status_code}): {preview}", "ok")
        else:
            flash(f"Matchup rejected ({result.status_code}): {preview}", "error")
        return redirect(request.referrer or url_for("index"))

    return app


def _form_source(form) -> dict | None:
    url = (form.get("url") or "").strip()
    if not _is_http_url(url):
        flash("Enter a public http:// or https:// URL.", "error")
        return None
    name = (form.get("name") or "").strip() or (urlparse(url).netloc or url)
    timeout_raw = (form.get("timeout") or "30").strip()
    table_raw = (form.get("table_index") or "").strip()
    try:
        timeout = float(timeout_raw)
        if timeout <= 0:
            raise ValueError
    except ValueError:
        flash("Timeout must be a positive number of seconds.", "error")
        return None
    table_index = None
    if table_raw:
        try:
            table_index = int(table_raw)
            if table_index < 0:
                raise ValueError
        except ValueError:
            flash("Table index must be a 0-based integer.", "error")
            return None
    return {
        "name": name,
        "url": url,
        "table_index": table_index,
        "timeout": timeout,
    }


def _matchup_payload_from_request() -> dict | None:
    if request.is_json:
        payload = request.get_json(silent=True)
    else:
        raw = (request.form.get("payload") or "").strip()
        if not raw:
            flash("Paste a matchup JSON payload first.", "error")
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            flash(f"Invalid matchup JSON: {exc}", "error")
            return None
    if not isinstance(payload, dict):
        flash("Matchup payload must be a JSON object.", "error")
        return None
    return payload


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _run_scrape(store: Store, source_id: int) -> None:
    source = store.get_source(source_id)
    if source is None:
        return
    try:
        tables = scrape_tables(source["url"], timeout=source["timeout"])
        selected = select_tables(tables, source["table_index"])
        payload = [
            {"index": index, "headers": table.unique_headers(), "rows": table.rows}
            for index, table in selected
        ]
        store.save_snapshot(source_id, payload)
        flash(f"Updated {source['name']}.", "ok")
    except (ScrapeError, IndexError) as exc:
        store.save_error(source_id, str(exc))
        flash(str(exc), "error")


def _tables_for_export(store: Store, source_id: int) -> list[Table] | None:
    snapshot = store.get_snapshot(source_id)
    if snapshot is None:
        flash("No data to export yet. Run a scrape first.", "error")
        return None
    return [
        Table(headers=item.get("headers") or [], rows=item.get("rows") or [])
        for item in snapshot["tables"]
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripscrap-web",
        description="Run the local scripscrap web UI.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=5000, help="Bind port")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
