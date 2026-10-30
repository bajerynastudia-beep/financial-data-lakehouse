"""Financial Modeling Prep: historyczne notowania cen dziennych (EOD) jako JSON.

Endpoint: https://financialmodelingprep.com/stable/historical-price-eod/full
Dostęp do symboli i dat zależy od planu FMP. Klucz pobieramy z Databricks Secrets.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Callable, Any

from fin_lakehouse.http_client import SourceError

BRONZE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]


class FmpError(SourceError):
    """Brak notowań, błąd API lub niepoprawny format odpowiedzi."""


def build_params(ticker: str, start: date, end: date, api_key: str) -> dict[str, str]:
    return {"symbol": ticker.upper(), "from": start.isoformat(), "to": end.isoformat(), "apikey": api_key}


def fetch_daily(http_get: Callable[..., Any], base_url: str, ticker: str,
                start: date, end: date, api_key: str) -> str:
    response = http_get(base_url, params=build_params(ticker, start, end, api_key))
    if response.status_code == 404:
        raise FmpError(f"FMP: HTTP 404, brak danych lub niedostępny endpoint dla {ticker}")
    return response.text


def parse_history(raw_json: str, ticker: str) -> list[dict[str, str | None]]:
    """Zwraca schemat Bronze zgodny z clean_prices w Silver."""
    raw = (raw_json or "").strip()
    if not raw or raw.startswith("<"):
        raise FmpError(f"FMP: odpowiedź HTML lub brak JSON dla {ticker}")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise FmpError(f"FMP: błędny JSON dla {ticker}") from exc
    if not isinstance(data, list):
        message = data.get("Error Message", data.get("message", str(data))) if isinstance(data, dict) else str(data)
        raise FmpError(f"FMP: API nie zwróciło listy notowań {ticker}: {str(message)[:150]}")
    if not data:
        raise FmpError(f"FMP: brak notowań dla {ticker}. Sprawdź daty, symbol i zakres planu.")

    rows = []
    for item in data:
        if not isinstance(item, dict) or str(item.get("symbol", "")).upper() != ticker.upper():
            raise FmpError(f"FMP: niezgodny symbol w rekordzie {ticker}")
        try:
            date.fromisoformat(str(item["date"]))
            if float(item["close"]) <= 0:
                raise ValueError("close <= 0")
        except (KeyError, TypeError, ValueError) as exc:
            raise FmpError(f"FMP: nieprawidłowa data lub cena zamknięcia dla {ticker}") from exc

        row = {"ticker": ticker.lower(), "date": str(item["date"])}
        for col in ("open", "high", "low", "close", "volume"):
            row[col] = None if item.get(col) is None else str(item[col])
        rows.append(row)
    return rows
