"""API NBP – średnie kursy walut (tabela A).

Dokumentacja: https://api.nbp.pl/
Endpoint: /api/exchangerates/rates/a/{kod}/{od}/{do}/?format=json
Ograniczenia API, które obsługujemy:
- jedno zapytanie może obejmować maksymalnie 93 dni -> dzielimy zakres na kawałki,
- brak notowań w danym okresie (weekend, święto) -> HTTP 404 "Brak danych" (to nie jest błąd).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Callable

BRONZE_COLUMNS = [
    "currency_code",
    "currency_name",
    "table_type",
    "table_no",
    "effective_date",
    "mid",
]


def date_chunks(start: date, end: date, max_days: int = 90) -> list[tuple[date, date]]:
    """Dzieli zakres [start, end] (włącznie) na kawałki po maksymalnie max_days dni."""
    if max_days < 1:
        raise ValueError("max_days musi być >= 1")
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def build_url(base_url: str, currency: str, start: date, end: date) -> str:
    return f"{base_url.rstrip('/')}/{currency.lower()}/{start.isoformat()}/{end.isoformat()}/"


def fetch_chunk(
    http_get: Callable[..., Any], base_url: str, currency: str, start: date, end: date
) -> str | None:
    """Pobiera jeden kawałek. Zwraca surowy tekst JSON albo None, gdy NBP zwraca 404 (brak danych)."""
    resp = http_get(build_url(base_url, currency, start, end), params={"format": "json"})
    if resp.status_code == 404:
        return None
    return resp.text


def parse_rates(raw_json: str) -> list[dict[str, str]]:
    """Zamienia odpowiedź NBP na wiersze warstwy Bronze (wartości jako tekst, bez interpretacji)."""
    payload = json.loads(raw_json)
    rows = []
    for rate in payload.get("rates", []):
        rows.append(
            {
                "currency_code": _s(payload.get("code")),
                "currency_name": _s(payload.get("currency")),
                "table_type": _s(payload.get("table")),
                "table_no": _s(rate.get("no")),
                "effective_date": _s(rate.get("effectiveDate")),
                "mid": _s(rate.get("mid")),
            }
        )
    return rows


def _s(value: Any) -> str | None:
    return None if value is None else str(value)
