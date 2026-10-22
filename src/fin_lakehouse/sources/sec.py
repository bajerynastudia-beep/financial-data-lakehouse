"""SEC EDGAR – dane ze sprawozdań finansowych spółek z USA (XBRL "company facts").

Dokumentacja: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Endpoint: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
Wymagania SEC: nagłówek User-Agent z nazwą i adresem kontaktowym, maks. 10 zapytań/s.

Pobieramy jedną miarę: rozwodniony zysk na akcję (us-gaap:EarningsPerShareDiluted, USD/akcję).
Każdy fakt ma okres (start-end), datę złożenia raportu (filed) i formularz (10-K roczny, 10-Q kwartalny).
Data `filed` jest kluczowa: pozwala liczyć P/E tylko z danych, które były znane w danym dniu.
"""

from __future__ import annotations

from typing import Any, Callable

from fin_lakehouse.http_client import SourceError

BRONZE_COLUMNS = [
    "cik",
    "entity_name",
    "concept",
    "unit",
    "period_start",
    "period_end",
    "val",
    "accn",
    "fy",
    "fp",
    "form",
    "filed",
    "frame",
]


def build_url(base_url: str, cik: int | str) -> str:
    return f"{base_url.rstrip('/')}/CIK{int(cik):010d}.json"


def fetch_company_facts(http_get: Callable[..., Any], base_url: str, cik: int | str, user_agent: str) -> str:
    resp = http_get(build_url(base_url, cik), headers={"User-Agent": user_agent, "Accept": "application/json"})
    if resp.status_code == 404:
        raise SourceError(f"SEC: brak danych dla CIK {cik}")
    return resp.text


def extract_facts(
    company_facts: dict[str, Any], concept: str = "EarningsPerShareDiluted", unit: str = "USD/shares"
) -> list[dict[str, str | None]]:
    """Wyciąga fakty jednej miary z pliku company facts jako wiersze Bronze (tekst, bez filtrowania)."""
    cik = company_facts.get("cik")
    entity = company_facts.get("entityName")
    node = company_facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if node is None:
        raise SourceError(f"SEC: spółka {entity} (CIK {cik}) nie raportuje miary {concept}")
    rows = []
    for fact in node.get("units", {}).get(unit, []):
        rows.append(
            {
                "cik": _s(cik),
                "entity_name": _s(entity),
                "concept": concept,
                "unit": unit,
                "period_start": _s(fact.get("start")),
                "period_end": _s(fact.get("end")),
                "val": _s(fact.get("val")),
                "accn": _s(fact.get("accn")),
                "fy": _s(fact.get("fy")),
                "fp": _s(fact.get("fp")),
                "form": _s(fact.get("form")),
                "filed": _s(fact.get("filed")),
                "frame": _s(fact.get("frame")),
            }
        )
    return rows


def _s(value: Any) -> str | None:
    return None if value is None else str(value)
