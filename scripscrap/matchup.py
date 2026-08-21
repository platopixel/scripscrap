"""POST a matchup payload to the add-matchup Cloud Run endpoint."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
