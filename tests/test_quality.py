"""Testy samych reguł jakości: czy wykrywają złe dane i przepuszczają dobre (wymagają PySpark)."""

from datetime import date

import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from fin_lakehouse.quality import checks as dq  # noqa: E402


@pytest.fixture
def prices(spark):
    return spark.createDataFrame(
        [
            ("pko", date(2024, 1, 2), 10.0, 11.0, 9.0, 10.5),
            ("pko", date(2024, 1, 3), 10.5, 10.0, 11.0, 10.2),  # low > high – błąd
            ("pko", date(2024, 1, 3), 10.5, 11.0, 10.0, 10.2),  # duplikat klucza
            ("xyz", date(2024, 1, 2), None, None, None, None),  # spoza słownika, brak ceny
            ("kgh", date(2024, 1, 2), 100.0, 101.0, 99.0, 100.0),
            ("kgh", date(2024, 1, 3), 300.0, 301.0, 299.0, 300.0),  # +200% w 1 dzień
        ],
        "ticker string, date date, open double, high double, low double, close double",
    )


def test_not_null_unique_referential(prices):
    assert dq.check_not_null(prices, "t", ["ticker", "close"]).failed_count == 1
    assert dq.check_unique(prices, "t", ["ticker", "date"]).failed_count == 1
    ref = dq.check_referential(prices, "t", "ticker", ["pko", "kgh"], "instruments")
    assert ref.failed_count == 1 and "xyz" in ref.details


def test_all_present_and_allowed_values(prices):
    missing = dq.check_all_present(prices, "t", "ticker", ["pko", "kgh", "pzu"])
    assert missing.failed_count == 1 and "pzu" in missing.details
    assert dq.check_allowed_values(prices, "t", "ticker", ["pko", "kgh"]).failed_count == 1


def test_domain_rules(prices):
    assert dq.check_ohlc_consistent(prices, "t").failed_count == 1
    moves = dq.check_daily_moves(prices.dropDuplicates(["ticker", "date"]), "t", 0.5)
    assert moves.failed_count == 1 and moves.status == "WARN"


def test_between_and_freshness(spark):
    fx = spark.createDataFrame(
        [("USD", date(2024, 1, 2), 4.0), ("EUR", date(2023, 12, 1), 40.0)], "currency string, date date, rate_mid double"
    )
    assert dq.check_between(fx, "t", "rate_mid", 0.5, 10).failed_count == 1
    stale = dq.check_freshness(fx, "t", "currency", "date", 7, today=date(2024, 1, 5))
    assert stale.failed_count == 1 and "EUR" in stale.details


def test_eps_split_suspect(spark):
    eps = spark.createDataFrame(
        [(1, date(2019, 7, 1), date(2020, 6, 30), 8.0, True), (1, date(2019, 7, 1), date(2020, 6, 30), 2.0, True),
         (2, date(2019, 1, 1), date(2019, 12, 31), 3.0, True), (2, date(2019, 1, 1), date(2019, 12, 31), 3.1, True)],
        "cik int, period_start date, period_end date, eps double, is_annual boolean",
    )
    assert dq.check_eps_split_suspect(eps, "t", 1.9).failed_count == 1


def test_enforce_fails_only_on_errors(spark):
    ok = dq.CheckResult("a", "t", "uniqueness", dq.ERROR, 0)
    warn = dq.CheckResult("b", "t", "domain", dq.WARN, 3)
    dq.enforce([ok, warn])  # ostrzeżenie nie przerywa potoku
    bad = dq.CheckResult("c", "t", "completeness", dq.ERROR, 2, "brak danych")
    with pytest.raises(dq.DataQualityError, match="c – 2"):
        dq.enforce([ok, warn, bad])
    assert [r.status for r in (ok, warn, bad)] == ["PASS", "WARN", "FAIL"]
    assert "FAIL" in dq.summarize([bad])


def test_condition_check(spark):
    df = spark.createDataFrame([(1,), (-1,)], "v int")
    r = dq.check_condition(df, "t", "v>0", "range", F.col("v") <= 0, dq.ERROR, ["v"])
    assert r.failed_count == 1 and r.details == "v=-1"
