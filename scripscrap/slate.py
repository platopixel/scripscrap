"""HTTP client for the weekly slate API (list / get / put duels)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from scripscrap.matchup import (
    MatchupPayload,
    MatchupValidationError,
    parse_matchup_payload,
)

URL_ENV_VAR = "SLATE_API_URL"
TOKEN_ENV_VAR = "SLATE_API_TOKEN"

_INT_RE = re.compile(r"-?\d+")


class SlateError(RuntimeError):
    """Raised when the slate API is unconfigured, unreachable, or invalid."""


@dataclass
class SlateResponse:
    status_code: int
    text: str
    data: Any | None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def base_url() -> str:
    """Return ``SLATE_API_URL`` with any trailing slash stripped."""
    value = os.environ.get(URL_ENV_VAR, "").strip().rstrip("/")
    if not value:
        raise SlateError(
            f"{URL_ENV_VAR} is not set. Set it to the slate API base URL."
        )
    return value


def list_weeks(*, timeout: float = 30.0) -> list[int]:
    """GET ``/slates`` and return sorted week numbers."""
    response = _request("GET", "/slates", timeout=timeout)
    data = _require_json_object(response, "List weeks")
    raw_weeks = data.get("weeks")
    if not isinstance(raw_weeks, list):
        raise SlateError("Slate list response must include a weeks array.")
    weeks: list[int] = []
    for index, item in enumerate(raw_weeks):
        weeks.append(_as_week_int(item, index))
    weeks.sort()
    return weeks


def get_week(week: int, *, timeout: float = 30.0) -> list[MatchupPayload]:
    """GET ``/slates/{week}`` and return validated duels."""
    response = _request("GET", f"/slates/{week}", timeout=timeout)
    data = _require_json_object(response, f"Get week {week}")
    raw_duels = data.get("duels")
    if not isinstance(raw_duels, list):
        raise SlateError(f"Week {week} response must include a duels array.")
    parsed: list[MatchupPayload] = []
    errors: list[str] = []
    for index, item in enumerate(raw_duels):
        raw = dict(item) if isinstance(item, dict) else item
        if isinstance(raw, dict) and "week" not in raw:
            raw["week"] = week
        try:
            parsed.append(parse_matchup_payload(raw))
        except MatchupValidationError as exc:
            errors.append(f"{_duel_label(index, raw)}: {exc}")
    if errors:
        raise SlateError("Invalid duel(s): " + "; ".join(errors))
    return parsed


def put_duel(
    payload: MatchupPayload,
    *,
    timeout: float = 30.0,
) -> SlateResponse:
    """PUT a full matchup to ``/slates/{week}/duels/{id}``.

    HTTP error statuses are returned on the response (the caller flashes).
    Network and config failures raise ``SlateError``.
    """
    week = payload["week"]
    duel_id = payload["id"]
    return _request(
        "PUT",
        f"/slates/{week}/duels/{duel_id}",
        json_body=payload,
        timeout=timeout,
    )


def _request(
    method: str,
    path: str,
    json_body: Any | None = None,
    *,
    timeout: float = 30.0,
) -> SlateResponse:
    url = base_url() + path
    headers = {"Accept": "application/json"}
    data: bytes | None = None
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _read_response(response.status, response.read())
    except urllib.error.HTTPError as exc:
        return _read_response(exc.code, exc.read())
    except urllib.error.URLError as exc:
        raise SlateError(f"Failed to reach slate API: {exc.reason}") from exc


def _read_response(status_code: int, raw: bytes) -> SlateResponse:
    text = raw.decode("utf-8", errors="replace")
    data: Any | None = None
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
    return SlateResponse(status_code=status_code, text=text, data=data)


def _require_json_object(response: SlateResponse, what: str) -> dict[str, Any]:
    if not response.ok:
        raise SlateError(f"{what} failed ({response.status_code}): {_preview(response.text)}")
    if not isinstance(response.data, dict):
        raise SlateError(f"{what} returned invalid JSON.")
    return response.data


def _as_week_int(value: Any, index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise SlateError(f"weeks[{index}] is not an integer.")
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text or not _INT_RE.fullmatch(text):
                raise ValueError
            value = int(text)
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise SlateError(f"weeks[{index}] is not an integer.") from exc
    if value < 1:
        raise SlateError(f"weeks[{index}] must be a positive integer.")
    return value


def _duel_label(index: int, item: Any) -> str:
    if isinstance(item, dict):
        duel_id = item.get("id")
        if isinstance(duel_id, str) and duel_id.strip():
            return f"duels[{index}] id={duel_id.strip()}"
    return f"duels[{index}]"


def _preview(text: str, limit: int = 240) -> str:
    preview = text.strip() or "(empty body)"
    if len(preview) > limit:
        return preview[:237] + "..."
    return preview
