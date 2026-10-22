"""Testy jednostkowe transformacji Bronze -> Silver (wymagają PySpark)."""

import json
from datetime import datetime

import pytest

pytest.importorskip("pyspark")

from pyspark.sql import types as T  # noqa: E402

from fin_lakehouse.sources import nbp, sec, stooq  # noqa: E402
from fin_lakehouse.transform import silver  # noqa: E402


def bronze(spark, columns, rows):
    """rows: lista (słownik_wartości, _ingest_ts)."""
    schema = T.StructType(
        [T.StructField(c, T.StringType()) for c in columns]
        + [T.StructField("_source_file", T.StringType()), T.StructField("_ingest_ts", T.TimestampType())]
    )
    data = [tuple(values.get(c) for c in columns) + ("test.json", ts) for values, ts in rows]
    return spark.createDataFrame(data, schema)


T1, T2 = datetime(2024, 1, 5, 10), datetime(2024, 1, 6, 10)


def test_clean_fx_types_dedupe_and_quarantine(spark):
    base = {"currency_code": "usd", "currency_name": "dolar", "table_type": "A", "table_no": "1"}
    df = bronze(spark, nbp.BRONZE_COLUMNS, [
        ({**base, "effective_date": "2024-01-02", "mid": "3.94"}, T1),
        ({**base, "effective_date": "2024-01-02", "mid": "3.95"}, T2),   # nowsza wersja tego samego dnia
        ({**base, "effective_date": "2024-01-03", "mid": "abc"}, T1),    # zły kurs
        ({**base, "effective_date": "2024-13-01", "mid": "3.90"}, T1),   # zła data
    ])
    valid, rejected = silver.clean_fx(df)
    rows = valid.collect()
    assert len(rows) == 1
    assert rows[0]["currency"] == "USD" and rows[0]["rate_mid"] == pytest.approx(3.95)
    reasons = sorted(r["_reject_reason"] for r in rejected.collect())
    assert reasons == ["invalid_date", "invalid_rate"]


def test_clean_prices_rejects_non_positive_close(spark):
    df = bronze(spark, stooq.BRONZE_COLUMNS, [
        ({"ticker": "PKO ", "date": "2024-01-02", "open": "1", "high": "2", "low": "1", "close": "1.5", "volume": "100"}, T1),
        ({"ticker": "pko", "date": "2024-01-03", "close": "0"}, T1),
        ({"ticker": None, "date": "2024-01-03", "close": "5"}, T1),
    ])
    valid, rejected = silver.clean_prices(df)
    v = valid.collect()
    assert [(r["ticker"], str(r["date"]), r["close"]) for r in v] == [("pko", "2024-01-02", 1.5)]
    assert sorted(r["_reject_reason"] for r in rejected.collect()) == ["missing_ticker", "non_positive_close"]


def test_clean_eps_marks_annual_reports(spark, fixtures):
    facts = json.loads((fixtures / "sec_companyfacts_sample.json").read_text())
    rows = [(r, T1) for r in sec.extract_facts(facts)]
    valid, rejected = silver.clean_eps(bronze(spark, sec.BRONZE_COLUMNS, rows))
    assert rejected.count() == 0
    by_key = {(str(r["period_end"]), r["accn"]): r for r in valid.collect()}
    assert len(by_key) == 4
    assert by_key[("2023-06-30", "0000950170-23-035122")]["is_annual"] is True
    assert by_key[("2023-09-30", "0000950170-23-054855")]["is_annual"] is False  # kwartał (10-Q)
    assert by_key[("2024-06-30", "0000950170-24-087843")]["eps"] == pytest.approx(11.80)


def test_quarantine_keeps_original_record(spark):
    df = bronze(spark, stooq.BRONZE_COLUMNS, [({"ticker": "pko", "date": "02.01.2024", "close": "1"}, T1)])
    _, rejected = silver.clean_prices(df)
    q = silver.to_quarantine(rejected, "bronze.stooq_prices").collect()[0]
    assert q["reject_reason"] == "invalid_date"
    assert json.loads(q["record_json"])["date"] == "02.01.2024"  # oryginalna, niepoprawna wartość
