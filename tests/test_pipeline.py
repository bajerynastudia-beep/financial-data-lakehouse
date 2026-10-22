"""Testy kroków potoku z podmienionymi źródłami i zapisem (wymagają PySpark)."""

from datetime import date

import pytest

pytest.importorskip("pyspark")

from conftest import FakeResponse  # noqa: E402
from fin_lakehouse import pipeline  # noqa: E402
from fin_lakehouse.config import load_config  # noqa: E402
from fin_lakehouse.http_client import SourceError  # noqa: E402


def test_as_date_tolerates_bad_watermark():
    assert pipeline._as_date("2024-01-05") == date(2024, 1, 5)
    assert pipeline._as_date("2024-01-05 10:00:00") == date(2024, 1, 5)
    assert pipeline._as_date("Data") is None
    assert pipeline._as_date(None) is None


def test_ingest_nbp_incremental_saves_raw_and_reports_errors(spark, repo_root, fixtures, monkeypatch, tmp_path):
    cfg = load_config(repo_root)
    captured = {}
    monkeypatch.setattr(pipeline.io, "max_by_group", lambda *a: {"USD": "2024-01-01", "EUR": "2024-01-01"})
    monkeypatch.setattr(pipeline.io, "append", lambda df, table: captured.update(df=df, table=table))
    monkeypatch.setattr(
        pipeline.io, "save_raw",
        lambda volume, source, name, text, day: str(tmp_path / name),
    )
    nbp_json = (fixtures / "nbp_usd_2024-01.json").read_text(encoding="utf-8")
    calls = []

    def http_get(url, params=None, headers=None):
        calls.append(url)
        if "/usd/" in url:
            return FakeResponse(200, nbp_json)
        raise SourceError("HTTP 500 po 5 próbach")

    res = pipeline.ingest_nbp(spark, cfg, "run-1", "incremental", end=date(2024, 1, 10), http_get=http_get)

    # przyrost: od dnia po ostatniej dacie w Bronze
    assert calls[0].endswith("/usd/2024-01-02/2024-01-10/")
    assert res.rows == 3 and res.files == 1
    assert len(res.errors) == 1 and res.errors[0].startswith("EUR")
    rows = captured["df"].collect()
    assert captured["table"] == "workspace.fin_bronze.nbp_fx_rates"
    assert {r["_run_id"] for r in rows} == {"run-1"}
    assert all(r["_source_file"].endswith(".json") for r in rows)
    with pytest.raises(SourceError, match="EUR"):
        res.raise_if_errors()
