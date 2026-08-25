"""POST a matchup payload to the add-matchup Cloud Run endpoint."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypedDict

ADD_MATCHUP_URL = "https://addmatchup-opaapgbaiq-uc.a.run.app"
TOKEN_ENV_VAR = "ADD_MATCHUP_TOKEN"


class PlayerPayload(TypedDict):
    slug: str
    name: str
    teamAbbr: str
    opponent: str
    pos: str
    proj: float


class MatchupPayload(TypedDict):
    week: int
    id: str
    lockedAtUtc: str
    freezeAtUtc: str
    playerA: PlayerPayload
    playerB: PlayerPayload


EXAMPLE_MATCHUP: MatchupPayload = {
    "week": 15,
    "id": "qb",
    "lockedAtUtc": "2026-12-14T18:00:00Z",
    "freezeAtUtc": "2026-12-17T17:00:00Z",
    "playerA": {
        "slug": "patrick-mahomes",
        "name": "Patrick Mahomes",
        "teamAbbr": "KC",
        "opponent": "@ LAC",
        "pos": "QB",
        "proj": 24.1,
    },
    "playerB": {
        "slug": "justin-herbert",
        "name": "Justin Herbert",
        "teamAbbr": "LAC",
        "opponent": "vs KC",
        "pos": "QB",
        "proj": 22.8,
    },
}

_UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?$")
_PLAYER_KEYS = ("slug", "name", "teamAbbr", "opponent", "pos", "proj")


class MatchupValidationError(ValueError):
    """Raised when a matchup payload does not match the expected format."""


def matchup_from_form(form: Mapping[str, Any]) -> dict[str, Any]:
    """Build a raw matchup dict from HTML form fields."""

    def player(prefix: str) -> dict[str, Any]:
        return {key: form.get(f"{prefix}_{key}") or "" for key in _PLAYER_KEYS}

    return {
        "week": form.get("week") or "",
        "id": form.get("id") or "",
        "lockedAtUtc": form.get("lockedAtUtc") or "",
        "freezeAtUtc": form.get("freezeAtUtc") or "",
        "playerA": player("playerA"),
        "playerB": player("playerB"),
    }


def parse_matchup_payload(raw: Any) -> MatchupPayload:
    """Validate *raw* and return a payload matching the example JSON shape."""
    if not isinstance(raw, dict):
        raise MatchupValidationError("Matchup payload must be a JSON object.")
    return {
        "week": _require_int(raw.get("week"), "week"),
        "id": _require_str(raw.get("id"), "id"),
        "lockedAtUtc": _require_utc(raw.get("lockedAtUtc"), "lockedAtUtc"),
        "freezeAtUtc": _require_utc(raw.get("freezeAtUtc"), "freezeAtUtc"),
        "playerA": _require_player(raw.get("playerA"), "playerA"),
        "playerB": _require_player(raw.get("playerB"), "playerB"),
    }


def _require_player(value: Any, field: str) -> PlayerPayload:
    if not isinstance(value, dict):
        raise MatchupValidationError(f"{field} must be an object.")
    return {
        "slug": _require_str(value.get("slug"), f"{field}.slug"),
        "name": _require_str(value.get("name"), f"{field}.name"),
        "teamAbbr": _require_str(value.get("teamAbbr"), f"{field}.teamAbbr"),
        "opponent": _require_str(value.get("opponent"), f"{field}.opponent"),
        "pos": _require_str(value.get("pos"), f"{field}.pos"),
        "proj": _require_float(value.get("proj"), f"{field}.proj"),
    }


def _require_str(value: Any, field: str) -> str:
    if value is None:
        raise MatchupValidationError(f"{field} is required.")
    if not isinstance(value, str):
        raise MatchupValidationError(f"{field} must be a string.")
    text = value.strip()
    if not text:
        raise MatchupValidationError(f"{field} is required.")
    return text


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise MatchupValidationError(f"{field} must be an integer.")
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise MatchupValidationError(f"{field} is required.")
            if not re.fullmatch(r"-?\d+", text):
                raise ValueError
            value = int(text)
        value = int(value)
        if value < 1:
            raise MatchupValidationError(f"{field} must be a positive integer.")
        return value
    except MatchupValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise MatchupValidationError(f"{field} must be an integer.") from exc


def _require_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise MatchupValidationError(f"{field} must be a number.")
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise MatchupValidationError(f"{field} is required.")
            value = float(text)
        return float(value)
    except MatchupValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise MatchupValidationError(f"{field} must be a number.") from exc


def _require_utc(value: Any, field: str) -> str:
    stamp = _require_str(value, field)
    if not _UTC_STAMP.fullmatch(stamp):
        raise MatchupValidationError(
            f"{field} must look like 2026-12-14T18:00:00Z."
        )
    if stamp.endswith("Z"):
        stamp = stamp[:-1]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", stamp):
        stamp += ":00"
    return stamp + "Z"


@dataclass
class MatchupResponse:
    status_code: int
    text: str
    data: Any | None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class MatchupError(RuntimeError):
    """Raised when the add-matchup request cannot be completed."""


def post_matchup(
    payload: MatchupPayload | dict[str, Any],
    *,
    timeout: float = 30.0,
    url: str = ADD_MATCHUP_URL,
) -> MatchupResponse:
    """POST *payload* as JSON to the add-matchup endpoint."""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _read_response(response.status, response.read())
    except urllib.error.HTTPError as exc:
        return _read_response(exc.code, exc.read())
    except urllib.error.URLError as exc:
        raise MatchupError(f"Failed to reach add-matchup endpoint: {exc.reason}") from exc


def _read_response(status_code: int, raw: bytes) -> MatchupResponse:
    text = raw.decode("utf-8", errors="replace")
    data: Any | None = None
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
    return MatchupResponse(status_code=status_code, text=text, data=data)
