"""Testy jakości danych uruchamiane w potoku.

Każdy test zwraca CheckResult. Wyniki są zapisywane do tabeli fin_ops.dq_results
i wypisywane w notatniku. Test o istotności "error", który nie przejdzie, przerywa
potok wyjątkiem DataQualityError -> zadanie w jobie kończy się błędem (widoczne dla
osoby uruchamiającej) i warstwa Gold NIE jest budowana ze złych danych.
Test o istotności "warn" jest tylko raportowany (status WARN).

Rodzaje reguł (rule_type): completeness, uniqueness, range, allowed_values,
referential_integrity, freshness, domain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import reduce
from typing import Iterable

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

ERROR = "error"
WARN = "warn"


class DataQualityError(RuntimeError):
    pass


@dataclass
class CheckResult:
    check_name: str
    table_name: str
    rule_type: str
    severity: str
    failed_count: int
    details: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> str:
        if self.failed_count == 0:
            return "PASS"
        return "FAIL" if self.severity == ERROR else "WARN"

    def as_row(self, run_id: str) -> dict:
        row = asdict(self)
        row["status"] = self.status
        row["run_id"] = run_id
        return row


def _sample(df: DataFrame, cols: list[str], n: int = 5) -> str:
    rows = df.select(*cols).limit(n).collect()
    return "; ".join(", ".join(f"{c}={r[c]}" for c in cols) for r in rows)


# --------------------------------------------------------------------------------------
# Reguły ogólne
# --------------------------------------------------------------------------------------
def check_not_null(df: DataFrame, table: str, cols: list[str], severity: str = ERROR) -> CheckResult:
    bad = df.filter(reduce(lambda a, b: a | b, [F.col(c).isNull() for c in cols]))
    n = bad.count()
    return CheckResult(f"not_null({','.join(cols)})", table, "completeness", severity, n,
                       _sample(bad, cols) if n else "")


def check_unique(df: DataFrame, table: str, keys: list[str], severity: str = ERROR) -> CheckResult:
    dups = df.groupBy(*keys).count().filter(F.col("count") > 1)
    n = dups.count()
    return CheckResult(f"unique({','.join(keys)})", table, "uniqueness", severity, n,
                       _sample(dups, keys + ["count"]) if n else "")


def check_between(df: DataFrame, table: str, col: str, lo: float, hi: float, severity: str = ERROR,
                  key_cols: list[str] | None = None) -> CheckResult:
    bad = df.filter(F.col(col).isNotNull() & ((F.col(col) < lo) | (F.col(col) > hi)))
    n = bad.count()
    return CheckResult(f"between({col},{lo},{hi})", table, "range", severity, n,
                       _sample(bad, (key_cols or []) + [col]) if n else "")


def check_allowed_values(df: DataFrame, table: str, col: str, allowed: Iterable[str],
                         severity: str = ERROR) -> CheckResult:
    allowed = list(allowed)
    bad = df.filter(F.col(col).isNotNull() & ~F.col(col).isin(allowed))
    n = bad.count()
    found = [r[col] for r in bad.select(col).distinct().limit(10).collect()] if n else []
    return CheckResult(f"allowed_values({col})", table, "allowed_values", severity, n,
                       f"niedozwolone: {found}" if n else "")


def check_condition(df: DataFrame, table: str, name: str, rule_type: str, is_bad: Column,
                    severity: str = ERROR, sample_cols: list[str] | None = None) -> CheckResult:
    """Dowolna reguła: is_bad = warunek oznaczający naruszenie."""
    bad = df.filter(is_bad)
    n = bad.count()
    return CheckResult(name, table, rule_type, severity, n,
                       _sample(bad, sample_cols) if (n and sample_cols) else "")


def check_referential(df: DataFrame, table: str, col: str, allowed: Iterable[str],
                      ref_name: str, severity: str = ERROR) -> CheckResult:
    """Każda wartość kolumny musi istnieć w słowniku (np. ticker w instruments.yml)."""
    allowed = list(allowed)
    orphans = [r[col] for r in df.select(col).distinct().filter(~F.col(col).isin(allowed)).collect()]
    return CheckResult(f"references({col}->{ref_name})", table, "referential_integrity", severity,
                       len(orphans), f"brak w {ref_name}: {sorted(map(str, orphans))}" if orphans else "")


def check_all_present(df: DataFrame, table: str, col: str, expected: Iterable[str],
                      severity: str = ERROR) -> CheckResult:
    """Każdy oczekiwany element (np. każdy instrument z konfiguracji) ma dane."""
    present = {r[col] for r in df.select(col).distinct().collect()}
    missing = sorted(set(expected) - present)
    return CheckResult(f"all_present({col})", table, "completeness", severity, len(missing),
                       f"brak danych dla: {missing}" if missing else "")


def check_freshness(df: DataFrame, table: str, group_col: str, date_col: str, max_age_days: int,
                    today: date | None = None, severity: str = WARN) -> CheckResult:
    """Najnowsza data w każdej grupie nie może być starsza niż max_age_days."""
    limit = (today or date.today()) - timedelta(days=max_age_days)
    stale = df.groupBy(group_col).agg(F.max(date_col).alias("last_date")).filter(F.col("last_date") < F.lit(limit))
    n = stale.count()
    return CheckResult(f"freshness({date_col},{max_age_days}d)", table, "freshness", severity, n,
                       _sample(stale, [group_col, "last_date"], 20) if n else "")


# --------------------------------------------------------------------------------------
# Reguły dziedzinowe
# --------------------------------------------------------------------------------------
def check_ohlc_consistent(prices: DataFrame, table: str, severity: str = WARN) -> CheckResult:
    """Cena najniższa <= otwarcia/zamknięcia <= najwyższa."""
    h, l, o, c = (F.col(x) for x in ("high", "low", "open", "close"))
    bad = (
        (h.isNotNull() & l.isNotNull() & (l > h))
        | (h.isNotNull() & (c > h * 1.0001))
        | (l.isNotNull() & (c < l * 0.9999))
        | (o.isNotNull() & h.isNotNull() & (o > h * 1.0001))
        | (o.isNotNull() & l.isNotNull() & (o < l * 0.9999))
    )
    return check_condition(prices, table, "ohlc_consistent", "domain", bad, severity,
                           ["ticker", "date", "open", "high", "low", "close"])


def check_daily_moves(prices: DataFrame, table: str, max_abs_return: float, severity: str = WARN) -> CheckResult:
    """Zmiana ceny między kolejnymi sesjami większa niż próg -> podejrzenie błędu lub niekorygowanego splitu."""
    from pyspark.sql import Window

    w = Window.partitionBy("ticker").orderBy("date")
    df = prices.withColumn("ret", F.col("close") / F.lag("close").over(w) - 1)
    return check_condition(df, table, f"abs_daily_return<={max_abs_return}", "domain",
                           F.abs(F.col("ret")) > max_abs_return, severity, ["ticker", "date", "close", "ret"])


def check_eps_split_suspect(eps: DataFrame, table: str, ratio_threshold: float, severity: str = WARN) -> CheckResult:
    """Ten sam okres EPS raportowany w różnych sprawozdaniach z wartościami różniącymi się
    o czynnik >= ratio_threshold -> spółka prawdopodobnie przeprowadziła split akcji
    (historyczne EPS przeliczono), a P/E z okresu przed splitem może być niespójne z cenami."""
    g = (
        eps.filter(F.col("is_annual") & (F.col("eps") > 0))
        .groupBy("cik", "period_start", "period_end")
        .agg(F.min("eps").alias("eps_min"), F.max("eps").alias("eps_max"))
        .filter(F.col("eps_max") / F.col("eps_min") >= ratio_threshold)
    )
    n = g.count()
    return CheckResult("eps_restatement_split_suspect", table, "domain", severity, n,
                       _sample(g, ["cik", "period_end", "eps_min", "eps_max"]) if n else "")


# --------------------------------------------------------------------------------------
# Wynik
# --------------------------------------------------------------------------------------
def summarize(results: list[CheckResult]) -> str:
    lines = [f"{'STATUS':6} | {'TABELA':40} | {'TEST':45} | {'RODZAJ':22} | BŁĘDNE"]
    for r in results:
        lines.append(f"{r.status:6} | {r.table_name:40} | {r.check_name:45} | {r.rule_type:22} | {r.failed_count}"
                     + (f"  -> {r.details}" if r.details else ""))
    return "\n".join(lines)


def enforce(results: list[CheckResult]) -> None:
    """Rzuca DataQualityError, jeśli którykolwiek test o istotności 'error' nie przeszedł."""
    failed = [r for r in results if r.status == "FAIL"]
    if failed:
        msg = "\n".join(f"- {r.table_name}: {r.check_name} – {r.failed_count} naruszeń. {r.details}" for r in failed)
        raise DataQualityError(f"{len(failed)} test(y) jakości danych nie przeszły:\n{msg}")
