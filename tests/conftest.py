"""Wspólna konfiguracja testów.

Testy modułów pobierania i konfiguracji działają bez Sparka.
Testy transformacji i jakości danych wymagają PySpark + Java (lokalnie lub w GitHub Actions);
bez PySpark są automatycznie pomijane.

Pliki w tests/fixtures/ to małe, syntetyczne próbki w formacie odpowiedzi źródeł.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def spark():
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("fin-lakehouse-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "true")  # jak na Databricks serverless
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = ""):
        self.status_code = status_code
        self.text = text


class FakeHttp:
    """Udaje funkcję http_get: zwraca przygotowane odpowiedzi i zapamiętuje wywołania."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params=None, headers=None, **_):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self.responses.pop(0)
