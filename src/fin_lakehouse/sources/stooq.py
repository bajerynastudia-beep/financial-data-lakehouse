"""Stooq – dzienne notowania (CSV).

Od 2026 r. Stooq wymaga klucza API do pobierania plików CSV (parametr `apikey`).
Klucz można uzyskać na stronie notowań instrumentu, np. https://stooq.com/q/d/?s=spy.us&get_apikey
Zamiast CSV Stooq potrafi zwrócić stronę HTML (brak/zły klucz) albo komunikat o limicie
dziennym – w obu przypadkach zgłaszamy czytelny błąd zamiast zapisywać śmieci.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any, Callable

from fin_lakehouse.http_client import SourceError

BRONZE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]

# Stooq zwraca nagłówki po angielsku (stooq.com) albo po polsku (stooq.pl)
_HEADER_MAP = {
    "date": "date", "data": "date",
    "open": "open", "otwarcie": "open",
    "high": "high", "najwyzszy": "high", "najwyższy": "high",
    "low": "low", "najnizszy": "low", "najniższy": "low",
    "close": "close", "zamkniecie": "close", "zamknięcie": "close",
    "volume": "volume", "wolumen": "volume",
}
_NO_DATA = {"no data", "brak danych"}


class StooqError(SourceError):
    pass


def build_params(ticker: str, start: date, end: date, api_key: str) -> dict[str, str]:
    return {
        "s": ticker,
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
        "apikey": api_key,
    }


def fetch_daily(
    http_get: Callable[..., Any], base_url: str, ticker: str, start: date, end: date, api_key: str
) -> str:
    resp = http_get(base_url, params=build_params(ticker, start, end, api_key))
    if resp.status_code == 404:
        raise StooqError(f"Stooq: nie znaleziono instrumentu {ticker}")
    return resp.text


def parse_csv(text: str, ticker: str) -> list[dict[str, str | None]]:
    """Waliduje odpowiedź i zamienia CSV na wiersze Bronze (wartości jako tekst)."""
    body = (text or "").strip().lstrip("﻿")
    if not body or body.lower() in _NO_DATA:
        return []
    low = body[:500].lower()
    if body.startswith("<") or "<html" in low:
        raise StooqError(
            f"Stooq zwrócił HTML zamiast CSV dla {ticker} – sprawdź klucz API (sekret stooq_api_key)."
        )
    if "limit" in low and "," not in body.splitlines()[0]:
        raise StooqError(f"Stooq: przekroczony limit zapytań ({body[:120]!r}). Spróbuj później.")

    reader = csv.DictReader(io.StringIO(body))
    mapping = {h: _HEADER_MAP.get(h.strip().lower()) for h in (reader.fieldnames or [])}
    if "date" not in mapping.values() or "close" not in mapping.values():
        raise StooqError(f"Stooq: nieoczekiwany format odpowiedzi dla {ticker}: {body[:120]!r}")

    rows = []
    for raw in reader:
        row: dict[str, str | None] = {c: None for c in BRONZE_COLUMNS}
        row["ticker"] = ticker
        for header, value in raw.items():
            col = mapping.get(header)
            if col:
                row[col] = value.strip() if isinstance(value, str) and value.strip() != "" else None
        rows.append(row)
    return rows
