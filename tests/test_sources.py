import json
from datetime import date

import pytest

from conftest import FakeHttp, FakeResponse
from fin_lakehouse.sources import nbp, sec, stooq


# ---------------- NBP ----------------
def test_date_chunks_respect_limit_and_cover_range():
    chunks = nbp.date_chunks(date(2019, 1, 1), date(2019, 12, 31), max_days=90)
    assert chunks[0][0] == date(2019, 1, 1) and chunks[-1][1] == date(2019, 12, 31)
    assert all((b - a).days + 1 <= 90 for a, b in chunks)
    # kawałki są ciągłe i się nie nakładają
    assert all((chunks[i + 1][0] - chunks[i][1]).days == 1 for i in range(len(chunks) - 1))


def test_date_chunks_empty_when_start_after_end():
    assert nbp.date_chunks(date(2024, 1, 2), date(2024, 1, 1)) == []


def test_nbp_parse_keeps_raw_values(fixtures):
    rows = nbp.parse_rates((fixtures / "nbp_usd_2024-01.json").read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert rows[0] == {
        "currency_code": "USD", "currency_name": "dolar amerykański", "table_type": "A",
        "table_no": "001/A/NBP/2024", "effective_date": "2024-01-02", "mid": "3.9432",
    }


def test_nbp_404_means_no_data():
    http = FakeHttp([FakeResponse(404, "404 NotFound - Not Found - Brak danych")])
    assert nbp.fetch_chunk(http, "https://api.nbp.pl/api/exchangerates/rates/a", "USD",
                           date(2024, 1, 6), date(2024, 1, 7)) is None
    assert http.calls[0]["url"].endswith("/usd/2024-01-06/2024-01-07/")


# ---------------- Stooq ----------------
def test_stooq_parse_english_csv(fixtures):
    rows = stooq.parse_csv((fixtures / "stooq_pko.csv").read_text(), "pko")
    assert len(rows) == 3
    assert rows[0]["ticker"] == "pko" and rows[0]["close"] == "45.8"
    assert rows[2]["volume"] is None  # pusty wolumen -> NULL, nie pusty tekst


def test_stooq_parse_polish_headers(fixtures):
    rows = stooq.parse_csv((fixtures / "stooq_wig20_pl.csv").read_text(), "wig20")
    assert rows == [{"ticker": "wig20", "date": "2024-01-02", "open": "2350.1", "high": "2370.5",
                     "low": "2340.0", "close": "2365.2", "volume": None}]


def test_stooq_html_instead_of_csv_is_clear_error(fixtures):
    with pytest.raises(stooq.StooqError, match="klucz API"):
        stooq.parse_csv((fixtures / "stooq_apikey_page.html").read_text(), "pko")


@pytest.mark.parametrize("text", ["No data", "Brak danych", ""])
def test_stooq_no_data_is_empty(text):
    assert stooq.parse_csv(text, "pko") == []


def test_stooq_daily_limit_is_error():
    with pytest.raises(stooq.StooqError, match="limit"):
        stooq.parse_csv("Przekroczony dzienny limit wywolan", "pko")


def test_stooq_request_params():
    http = FakeHttp([FakeResponse(200, "Date,Close\n2024-01-02,1")])
    stooq.fetch_daily(http, "https://stooq.com/q/d/l/", "msft.us", date(2024, 1, 1), date(2024, 1, 31), "KEY")
    assert http.calls[0]["params"] == {"s": "msft.us", "i": "d", "d1": "20240101", "d2": "20240131", "apikey": "KEY"}


# ---------------- SEC ----------------
def test_sec_url_pads_cik():
    assert sec.build_url("https://data.sec.gov/api/xbrl/companyfacts", 789019).endswith("/CIK0000789019.json")


def test_sec_extract_eps_facts(fixtures):
    facts = json.loads((fixtures / "sec_companyfacts_sample.json").read_text())
    rows = sec.extract_facts(facts)
    assert len(rows) == 4
    first = rows[0]
    assert first["cik"] == "789019" and first["form"] == "10-K"
    assert (first["period_start"], first["period_end"], first["val"]) == ("2022-07-01", "2023-06-30", "9.68")
    assert rows[3]["frame"] is None  # brak pola w źródle -> NULL


def test_sec_missing_concept_is_error(fixtures):
    facts = json.loads((fixtures / "sec_companyfacts_sample.json").read_text())
    with pytest.raises(Exception, match="nie raportuje"):
        sec.extract_facts(facts, concept="NieMaTakiejMiary")


def test_sec_sends_user_agent():
    http = FakeHttp([FakeResponse(200, "{}")])
    sec.fetch_company_facts(http, "https://data.sec.gov/api/xbrl/companyfacts", 21344, "Fundusz test@example.com")
    assert http.calls[0]["headers"]["User-Agent"] == "Fundusz test@example.com"
