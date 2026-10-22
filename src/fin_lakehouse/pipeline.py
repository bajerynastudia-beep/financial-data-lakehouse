"""Kroki potoku wywoływane z notatników Databricks (notebooks/0*_*.py).

Każdy krok jest funkcją, dzięki czemu notatniki są krótkie, a logika jest w jednym miejscu,
w kodzie objętym kontrolą wersji i testami.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import partial
from typing import Any, Callable

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from fin_lakehouse import lakehouse_io as io
from fin_lakehouse.config import Config, get_secret
from fin_lakehouse.http_client import SourceError, get_with_retry
from fin_lakehouse.quality import checks as dq
from fin_lakehouse.sources import nbp, sec, stooq
from fin_lakehouse.transform import gold, silver

# Nazwy tabel (bez katalogu i schematu)
BRONZE = {"fx": "nbp_fx_rates", "prices": "stooq_prices", "eps": "sec_eps_facts"}
SILVER = {"fx": "fx_rates", "prices": "prices", "eps": "eps_facts", "quarantine": "quarantine"}
OPS = {"runs": "pipeline_runs", "dq": "dq_results"}


@dataclass
class StepResult:
    step: str
    rows: int = 0
    files: int = 0
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def raise_if_errors(self) -> None:
        if self.errors:
            raise SourceError(f"{self.step}: {len(self.errors)} błąd(y) pobierania:\n- " + "\n- ".join(self.errors))


def http_getter(cfg: Config) -> Callable[..., Any]:
    h = cfg.settings["http"]
    return partial(get_with_retry, timeout_s=h["timeout_s"], max_retries=h["max_retries"], backoff_s=h["backoff_s"])


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


# --------------------------------------------------------------------------------------
# 0. Przygotowanie środowiska i test połączenia ze źródłami
# --------------------------------------------------------------------------------------
def setup(spark: SparkSession, cfg: Config) -> None:
    for layer in ("bronze", "silver", "gold", "ops"):
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg.schema(layer)}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {cfg.schema('bronze')}.{cfg.settings['raw_volume']}")


def check_sources(cfg: Config, dbutils: Any = None, http_get: Callable[..., Any] | None = None) -> list[dict[str, str]]:
    """Krótki test, czy z tego środowiska działają wszystkie źródła i sekrety."""
    http_get = http_get or partial(get_with_retry, timeout_s=15, max_retries=0)
    src = cfg.settings["sources"]
    today = date.today()
    out = []

    def probe(name: str, fn: Callable[[], str]) -> None:
        try:
            out.append({"source": name, "status": "OK", "message": fn()})
        except Exception as exc:  # raport, nie przerywamy
            out.append({"source": name, "status": "BŁĄD", "message": f"{type(exc).__name__}: {exc}"[:300]})

    def _nbp() -> str:
        raw = nbp.fetch_chunk(http_get, src["nbp"]["base_url"], "USD", today - timedelta(days=10), today)
        return f"{len(nbp.parse_rates(raw)) if raw else 0} kursów USD z ostatnich 10 dni"

    def _stooq() -> str:
        key = get_secret(cfg, "stooq_api_key", dbutils)
        txt = stooq.fetch_daily(http_get, src["stooq"]["base_url"], cfg.tickers[0], today - timedelta(days=10), today, key)
        return f"{len(stooq.parse_csv(txt, cfg.tickers[0]))} notowań {cfg.tickers[0]} z ostatnich 10 dni"

    def _sec() -> str:
        ua = get_secret(cfg, "sec_user_agent", dbutils)
        comp = cfg.sec_companies[0]
        facts = json.loads(sec.fetch_company_facts(http_get, src["sec"]["base_url"], comp["sec_cik"], ua))
        return f"{len(sec.extract_facts(facts, src['sec']['concept'], src['sec']['unit']))} faktów EPS dla {comp['name']}"

    probe("NBP (kursy walut)", _nbp)
    probe("Stooq (notowania)", _stooq)
    probe("SEC EDGAR (EPS)", _sec)
    return out


# --------------------------------------------------------------------------------------
# 1. Pozyskanie -> Bronze
# --------------------------------------------------------------------------------------
def ingest_nbp(spark: SparkSession, cfg: Config, run_id: str, mode: str = "incremental",
               end: date | None = None, http_get: Callable[..., Any] | None = None) -> StepResult:
    s, src = cfg.settings, cfg.settings["sources"]["nbp"]
    table = cfg.table("bronze", BRONZE["fx"])
    http_get = http_get or http_getter(cfg)
    today = date.today()
    end = end or today
    wm = io.max_by_group(spark, table, "currency_code", "effective_date") if mode == "incremental" else {}
    res = StepResult("ingest_nbp")
    rows: list[dict] = []
    for cur in src["currencies"]:
        start = (date.fromisoformat(wm[cur]) + timedelta(days=1)) if wm.get(cur) else date.fromisoformat(s["history_start"])
        for a, b in nbp.date_chunks(start, end, src["max_days_per_request"]):
            try:
                raw = nbp.fetch_chunk(http_get, src["base_url"], cur, a, b)
                if raw is None:  # 404 = brak notowań w tym okresie
                    continue
                parsed = nbp.parse_rates(raw)
            except (SourceError, ValueError) as exc:
                res.errors.append(f"{cur} {a}..{b}: {exc}")
                continue
            path = io.save_raw(cfg.raw_volume_path, "nbp", f"{cur}_{a}_{b}_{_safe(run_id)}.json", raw, today.isoformat())
            res.files += 1
            for r in parsed:
                r["_source_file"] = path
            rows += parsed
    if rows:
        io.append(io.rows_to_bronze(spark, rows, nbp.BRONZE_COLUMNS, run_id), table)
    res.rows = len(rows)
    return res


def ingest_stooq(spark: SparkSession, cfg: Config, run_id: str, mode: str = "incremental", dbutils: Any = None,
                 end: date | None = None, http_get: Callable[..., Any] | None = None) -> StepResult:
    s, src = cfg.settings, cfg.settings["sources"]["stooq"]
    table = cfg.table("bronze", BRONZE["prices"])
    http_get = http_get or http_getter(cfg)
    api_key = get_secret(cfg, "stooq_api_key", dbutils)
    today = date.today()
    end = end or today
    wm = io.max_by_group(spark, table, "ticker", "date") if mode == "incremental" else {}
    res = StepResult("ingest_stooq")
    rows: list[dict] = []
    for ticker in cfg.tickers:
        if wm.get(ticker):
            start = date.fromisoformat(wm[ticker]) - timedelta(days=src["overlap_days"])
        else:
            start = date.fromisoformat(s["history_start"])
        try:
            text = stooq.fetch_daily(http_get, src["base_url"], ticker, start, end, api_key)
            parsed = stooq.parse_csv(text, ticker)
        except SourceError as exc:
            res.errors.append(f"{ticker}: {exc}")
            continue
        path = io.save_raw(cfg.raw_volume_path, "stooq", f"{_safe(ticker)}_{start}_{end}_{_safe(run_id)}.csv", text, today.isoformat())
        res.files += 1
        for r in parsed:
            r["_source_file"] = path
        rows += parsed
    if rows:
        io.append(io.rows_to_bronze(spark, rows, stooq.BRONZE_COLUMNS, run_id), table)
    res.rows = len(rows)
    return res


def ingest_sec(spark: SparkSession, cfg: Config, run_id: str, mode: str = "incremental", dbutils: Any = None,
               http_get: Callable[..., Any] | None = None, sleep: Callable[[float], None] = time.sleep) -> StepResult:
    """SEC udostępnia pełny stan danych spółki (bez przyrostów) – pobieramy całość, a w trybie
    przyrostowym najwyżej raz dziennie na spółkę. Duplikaty usuwa warstwa Silver."""
    src = cfg.settings["sources"]["sec"]
    table = cfg.table("bronze", BRONZE["eps"])
    http_get = http_get or http_getter(cfg)
    user_agent = get_secret(cfg, "sec_user_agent", dbutils)
    today = date.today()
    last = io.max_by_group(spark, table, "cik", "_ingest_ts") if mode == "incremental" else {}
    res = StepResult("ingest_sec")
    rows: list[dict] = []
    for comp in cfg.sec_companies:
        cik = str(int(comp["sec_cik"]))
        if last.get(cik) and last[cik].date() >= today:
            res.details.setdefault("skipped_today", []).append(comp["ticker"])
            continue
        try:
            text = sec.fetch_company_facts(http_get, src["base_url"], cik, user_agent)
            parsed = sec.extract_facts(json.loads(text), src["concept"], src["unit"])
        except (SourceError, ValueError) as exc:
            res.errors.append(f"{comp['ticker']} (CIK {cik}): {exc}")
            continue
        path = io.save_raw(cfg.raw_volume_path, "sec", f"CIK{int(cik):010d}_{_safe(run_id)}.json", text, today.isoformat())
        res.files += 1
        for r in parsed:
            r["_source_file"] = path
        rows += parsed
        sleep(src["pause_between_requests_s"])
    if rows:
        io.append(io.rows_to_bronze(spark, rows, sec.BRONZE_COLUMNS, run_id), table)
    res.rows = len(rows)
    return res


# --------------------------------------------------------------------------------------
# 2. Bronze -> Silver
# --------------------------------------------------------------------------------------
_SILVER_SPECS = [
    ("fx", silver.clean_fx, silver.FX_KEYS),
    ("prices", silver.clean_prices, silver.PRICE_KEYS),
    ("eps", silver.clean_eps, silver.EPS_KEYS),
]


def build_silver(spark: SparkSession, cfg: Config, run_id: str, mode: str = "incremental") -> StepResult:
    """Przetwarza tylko rekordy Bronze nowsze niż ostatnio przetworzone (tryb przyrostowy)
    albo wszystkie (mode='full'). Zapis MERGE -> wynik nie zależy od liczby uruchomień."""
    res = StepResult("build_silver")
    quarantine_table = cfg.table("silver", SILVER["quarantine"])
    for name, cleaner, keys in _SILVER_SPECS:
        bronze_table = cfg.table("bronze", BRONZE[name])
        silver_table = cfg.table("silver", SILVER[name])
        if not io.table_exists(spark, bronze_table):
            res.errors.append(f"Brak tabeli {bronze_table} – uruchom najpierw pobieranie danych")
            continue
        src = spark.table(bronze_table)
        wm = io.max_value(spark, silver_table, "_ingest_ts") if mode == "incremental" else None
        if wm is not None:
            src = src.filter(F.col("_ingest_ts") > F.lit(wm))
        valid, rejected = cleaner(src)
        n_valid, n_rejected = valid.count(), rejected.count()
        if n_valid:
            io.merge_upsert(spark, valid, silver_table, keys)
        if n_rejected:
            io.append(silver.to_quarantine(rejected, bronze_table), quarantine_table)
        res.details[name] = {"valid": n_valid, "rejected": n_rejected}
        res.rows += n_valid
    return res


# --------------------------------------------------------------------------------------
# 3. Testy jakości danych Silver (bramka przed Gold)
# --------------------------------------------------------------------------------------
def silver_quality_checks(spark: SparkSession, cfg: Config, today: date | None = None) -> list[dq.CheckResult]:
    q = cfg.settings["quality"]
    t_fx, t_px, t_eps = (cfg.table("silver", SILVER[k]) for k in ("fx", "prices", "eps"))
    fx, px, eps = spark.table(t_fx), spark.table(t_px), spark.table(t_eps)
    ciks = [int(c["sec_cik"]) for c in cfg.sec_companies]
    return [
        # kursy walut
        dq.check_not_null(fx, t_fx, ["currency", "date", "rate_mid"]),
        dq.check_unique(fx, t_fx, silver.FX_KEYS),
        dq.check_allowed_values(fx, t_fx, "currency", cfg.settings["sources"]["nbp"]["currencies"]),
        dq.check_between(fx, t_fx, "rate_mid", q["fx_rate_min"], q["fx_rate_max"], key_cols=["currency", "date"]),
        dq.check_freshness(fx, t_fx, "currency", "date", q["freshness_max_days"], today),
        # notowania
        dq.check_not_null(px, t_px, ["ticker", "date", "close"]),
        dq.check_unique(px, t_px, silver.PRICE_KEYS),
        dq.check_referential(px, t_px, "ticker", cfg.tickers, "config/instruments.yml"),
        dq.check_all_present(px, t_px, "ticker", cfg.tickers),
        dq.check_ohlc_consistent(px, t_px),
        dq.check_daily_moves(px, t_px, q["max_abs_daily_return"]),
        dq.check_freshness(px, t_px, "ticker", "date", q["freshness_max_days"], today),
        # zyski na akcję (SEC)
        dq.check_unique(eps, t_eps, silver.EPS_KEYS),
        dq.check_all_present(eps.filter(F.col("is_annual")), t_eps, "cik", ciks),
        dq.check_eps_split_suspect(eps, t_eps, q["split_ratio_threshold"]),
    ]


def run_quality(spark: SparkSession, cfg: Config, run_id: str, results: list[dq.CheckResult]) -> str:
    """Zapisuje wyniki, zwraca czytelne podsumowanie, a przy błędach krytycznych przerywa potok."""
    io.write_dq_results(spark, cfg.table("ops", OPS["dq"]), results, run_id)
    summary = dq.summarize(results)
    print(summary)
    dq.enforce(results)
    return summary


# --------------------------------------------------------------------------------------
# 4. Silver -> Gold
# --------------------------------------------------------------------------------------
def build_gold(spark: SparkSession, cfg: Config) -> tuple[StepResult, list[dq.CheckResult]]:
    a, p = cfg.settings["analytics"], cfg.portfolio
    weights = cfg.portfolio_weights
    fx = spark.table(cfg.table("silver", SILVER["fx"]))
    prices = spark.table(cfg.table("silver", SILVER["prices"])).filter(F.col("ticker").isin(cfg.tickers))
    eps = spark.table(cfg.table("silver", SILVER["eps"]))

    res = StepResult("build_gold")

    def save(name: str, df):
        """Zapis tabeli Gold i ponowny odczyt – kolejne kroki czytają już zapisany wynik
        (na serverless nie ma df.cache(), a tak unikamy wielokrotnego przeliczania)."""
        io.overwrite(df, cfg.table("gold", name))
        saved = spark.table(cfg.table("gold", name))
        res.details[name] = saved.count()
        return saved

    dim_instrument = save("dim_instrument", gold.build_dim_instrument(spark, cfg.instruments, weights))
    calendar = gold.trading_calendar(prices)
    save("dim_date", gold.build_dim_date(calendar))
    fx_daily = save("fact_fx_daily", gold.build_fx_daily(fx, calendar))
    prices_daily = save("fact_prices_daily", gold.build_prices_daily(prices, fx_daily, dim_instrument))
    valuation_daily = save("fact_valuation_daily", gold.build_valuation_daily(prices_daily, eps, dim_instrument))
    save("valuation_snapshot", gold.build_valuation_snapshot(valuation_daily, dim_instrument))
    positions = save(
        "portfolio_positions_daily",
        gold.build_portfolio_positions_daily(prices_daily, weights, p["start_date"], p["initial_capital_pln"]),
    )
    portfolio_daily = save(
        "portfolio_daily",
        gold.build_portfolio_daily(positions, p["initial_capital_pln"], a["trading_days_per_year"], a["rolling_window_days"]),
    )
    save(
        "risk_return",
        gold.build_risk_return(prices_daily, portfolio_daily, dim_instrument, p["name"], a["risk_free_rate"], a["trading_days_per_year"]),
    )
    res.rows = sum(res.details.values())
    tables = list(res.details)

    g = {k: spark.table(cfg.table("gold", k)) for k in tables}
    t = {k: cfg.table("gold", k) for k in tables}
    results = [
        dq.check_not_null(g["fact_prices_daily"], t["fact_prices_daily"], ["fx_rate", "close_pln"]),
        dq.check_unique(g["fact_prices_daily"], t["fact_prices_daily"], ["ticker", "date"]),
        dq.check_condition(g["portfolio_daily"], t["portfolio_daily"], f"n_positions=={len(weights)}",
                           "completeness", F.col("n_positions") != len(weights), dq.ERROR, ["date", "n_positions"]),
        dq.check_condition(g["portfolio_daily"], t["portfolio_daily"], "value_pln>0", "range",
                           F.col("value_pln") <= 0, dq.ERROR, ["date", "value_pln"]),
        dq.check_unique(g["risk_return"], t["risk_return"], ["ticker"]),
        dq.check_between(g["fact_valuation_daily"], t["fact_valuation_daily"], "pe_ratio", 0, 300, dq.WARN, ["ticker", "date"]),
        dq.check_condition(g["valuation_snapshot"], t["valuation_snapshot"], "eps_age_days<=550", "freshness",
                           F.datediff("as_of_date", "eps_period_end") > 550, dq.WARN, ["ticker", "eps_period_end"]),
    ]
    return res, results
