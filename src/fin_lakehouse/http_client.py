"""Wspólny klient HTTP: limity czasu, ponawianie z rosnącym odstępem, czytelne błędy."""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping

import requests

RETRY_STATUSES = {429, 500, 502, 503, 504}


class SourceError(RuntimeError):
    """Błąd źródła danych, którego nie da się naprawić ponowieniem (np. zły klucz, 400)."""


def get_with_retry(
    url: str,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_s: float = 30,
    max_retries: int = 4,
    backoff_s: float = 2,
    session: Any = None,
    sleep: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET z ponawianiem dla błędów przejściowych (sieć, 429, 5xx).

    - 404 jest zwracane bez wyjątku – dla API NBP oznacza "brak danych w tym okresie".
    - inne 4xx -> SourceError (ponawianie nic nie da).
    - po wyczerpaniu prób -> SourceError z opisem ostatniego błędu.
    """
    http = session or requests
    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            resp = http.get(url, params=params, headers=headers, timeout=timeout_s)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code < 400 or resp.status_code == 404:
                return resp
            if resp.status_code not in RETRY_STATUSES:
                raise SourceError(f"HTTP {resp.status_code} dla {url}: {resp.text[:200]}")
            last_error = f"HTTP {resp.status_code}"
        if attempt < max_retries:
            sleep(backoff_s * (2**attempt))
    raise SourceError(f"Nie udało się pobrać {url} po {max_retries + 1} próbach ({last_error})")
