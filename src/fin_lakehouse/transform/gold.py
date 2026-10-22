"""Silver -> Gold: model analityczny dla zespołu inwestycyjnego funduszu.

Tabele Gold (pełna przebudowa przy każdym uruchomieniu – są w 100% wyliczane z Silver):
- dim_instrument            słownik spółek i indeksów (z config/instruments.yml + wagi portfela)
- dim_date                  kalendarz z flagą dnia sesyjnego
- fact_fx_daily             kurs NBP na każdy dzień sesyjny (uzupełniony ostatnim znanym kursem)
- fact_prices_daily         ceny w walucie notowania i w PLN, dzienne stopy zwrotu
- fact_valuation_daily      P/E i stopa zysku (earnings yield) spółek z USA – tylko dane znane w danym dniu
- valuation_snapshot        bieżące P/E na tle własnej historii (mediana, percentyl) – screening spółek
- portfolio_positions_daily wartość każdej pozycji portfela modelowego w PLN, efekt kursowy
- portfolio_daily           wartość portfela, zwrot, obsunięcie kapitału (drawdown), zmienność krocząca
- risk_return               stopa zwrotu, zmienność, zwrot/ryzyko, max drawdown – spółki, indeksy, portfel
"""

from __future__ import annotations

import math
from typing import Any

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

PORTFOLIO_KEY = "PORTFEL"

DIM_INSTRUMENT_SCHEMA = T.StructType(
    [
        T.StructField("ticker", T.StringType(), False),
        T.StructField("name", T.StringType(), True),
        T.StructField("market", T.StringType(), True),
        T.StructField("currency", T.StringType(), True),
        T.StructField("instrument_type", T.StringType(), True),
        T.StructField("sector", T.StringType(), True),
        T.StructField("sec_cik", T.IntegerType(), True),
        T.StructField("in_portfolio", T.BooleanType(), False),
        T.StructField("portfolio_weight", T.DoubleType(), False),
    ]
)


# --------------------------------------------------------------------------------------
# Wymiary
# --------------------------------------------------------------------------------------
def build_dim_instrument(spark, instruments: list[dict[str, Any]], weights: dict[str, float]) -> DataFrame:
    rows = [
        (
            i["ticker"],
            i.get("name"),
            i.get("market"),
            i.get("currency"),
            i.get("type"),
            i.get("sector"),
            int(i["sec_cik"]) if i.get("sec_cik") else None,
            i["ticker"] in weights,
            float(weights.get(i["ticker"], 0.0)),
        )
        for i in instruments
    ]
    return spark.createDataFrame(rows, DIM_INSTRUMENT_SCHEMA)


def trading_calendar(prices: DataFrame) -> DataFrame:
    """Dni sesyjne = dni, w których notowany był co najmniej jeden instrument."""
    return prices.select("date").distinct()


def build_dim_date(calendar: DataFrame) -> DataFrame:
    bounds = calendar.agg(F.min("date").alias("d0"), F.max("date").alias("d1"))
    days = bounds.select(F.explode(F.sequence(F.col("d0"), F.col("d1"))).alias("date"))
    trading = calendar.withColumn("is_trading_day", F.lit(True))
    return (
        days.join(trading, "date", "left")
        .withColumn("is_trading_day", F.coalesce(F.col("is_trading_day"), F.lit(False)))
        .withColumn("year", F.year("date"))
        .withColumn("quarter", F.quarter("date"))
        .withColumn("month", F.month("date"))
        .withColumn("year_month", F.date_format("date", "yyyy-MM"))
        .withColumn("day_of_week", F.dayofweek("date"))  # 1 = niedziela, 7 = sobota
    )


# --------------------------------------------------------------------------------------
# Fakty: kursy i ceny
# --------------------------------------------------------------------------------------
def _forward_fill(df: DataFrame, key: str, value_cols: list[str], flag_col: str) -> DataFrame:
    """Uzupełnia brakujące wartości ostatnią znaną wartością w obrębie klucza (po dacie)."""
    w = Window.partitionBy(key).orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    out = df.withColumn(flag_col, F.col(value_cols[0]).isNull())
    for c in value_cols:
        out = out.withColumn(c, F.last(c, ignorenulls=True).over(w))
    return out.filter(F.col(value_cols[0]).isNotNull())


def build_fx_daily(fx: DataFrame, calendar: DataFrame) -> DataFrame:
    """Kurs średni NBP dla każdego dnia sesyjnego.

    NBP nie publikuje kursów w polskie święta, a giełdy zagraniczne mogą wtedy działać –
    używamy ostatniego opublikowanego kursu (fx_is_filled = True). PLN ma kurs 1.
    """
    grid = fx.select("currency").distinct().crossJoin(calendar)
    joined = grid.join(fx.select("currency", "date", "rate_mid"), ["currency", "date"], "left")
    filled = _forward_fill(joined, "currency", ["rate_mid"], "fx_is_filled")
    pln = calendar.select(
        F.lit("PLN").alias("currency"),
        F.col("date"),
        F.lit(1.0).alias("rate_mid"),
        F.lit(False).alias("fx_is_filled"),
    )
    return filled.select("currency", "date", "rate_mid", "fx_is_filled").unionByName(pln)


def build_prices_daily(prices: DataFrame, fx_daily: DataFrame, dim_instrument: DataFrame) -> DataFrame:
    """Ceny na wspólnym kalendarzu sesyjnym, przeliczone na PLN kursem NBP z tego samego dnia."""
    calendar = trading_calendar(prices)
    grid = prices.select("ticker").distinct().crossJoin(calendar)
    joined = grid.join(prices.select("ticker", "date", "close", "volume"), ["ticker", "date"], "left")
    filled = _forward_fill(joined, "ticker", ["close"], "is_filled")
    filled = filled.withColumn("volume", F.when(F.col("is_filled"), F.lit(None)).otherwise(F.col("volume")))

    df = filled.join(dim_instrument.select("ticker", "currency", "instrument_type"), "ticker").join(
        fx_daily.select("currency", "date", F.col("rate_mid").alias("fx_rate"), "fx_is_filled"),
        ["currency", "date"],
        "left",
    )
    df = df.withColumn("close_pln", F.col("close") * F.col("fx_rate"))
    w = Window.partitionBy("ticker").orderBy("date")
    return (
        df.withColumn("daily_return_local", F.col("close") / F.lag("close").over(w) - 1)
        .withColumn("daily_return_pln", F.col("close_pln") / F.lag("close_pln").over(w) - 1)
        .select(
            "date", "ticker", "instrument_type", "currency", "close", "volume", "fx_rate",
            "close_pln", "daily_return_local", "daily_return_pln", "is_filled", "fx_is_filled",
        )
    )


# --------------------------------------------------------------------------------------
# Wycena: P/E
# --------------------------------------------------------------------------------------
def build_valuation_daily(prices_daily: DataFrame, eps: DataFrame, dim_instrument: DataFrame) -> DataFrame:
    """P/E = cena / roczny rozwodniony EPS z OSTATNIEGO raportu rocznego znanego w danym dniu.

    Reguły dziedzinowe:
    - bierzemy tylko raporty złożone (filed) najpóźniej w dniu wyceny -> brak "zaglądania w przyszłość",
    - spośród nich: najpóźniejszy okres (period_end), a dla niego najnowsza wersja (korekty, przekształcenia),
    - P/E ma sens tylko dla dodatniego zysku: przy EPS <= 0 zostawiamy NULL (stopa zysku nadal liczona),
    - cena i EPS są w tej samej walucie (USD), więc P/E nie zależy od kursu walut.
    """
    companies = dim_instrument.filter(F.col("sec_cik").isNotNull()).select("ticker", F.col("sec_cik").alias("cik"))
    events = (
        eps.filter(F.col("is_annual"))
        .join(companies, "cik")
        .select(
            F.col("ticker").alias("_e_ticker"),
            F.col("period_end").alias("eps_period_end"),
            F.col("filed").alias("eps_filed"),
            F.col("eps").alias("eps_annual"),
            F.col("form").alias("eps_form"),
        )
    )
    px = prices_daily.join(companies.select("ticker"), "ticker").select("date", "ticker", "currency", "close", "is_filled")
    joined = px.join(
        events,
        (F.col("ticker") == F.col("_e_ticker")) & (F.col("eps_filed") <= F.col("date")),
        "left",
    )
    w = Window.partitionBy("ticker", "date").orderBy(
        F.col("eps_period_end").desc_nulls_last(), F.col("eps_filed").desc_nulls_last()
    )
    latest = joined.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1)
    return latest.select(
        "date",
        "ticker",
        "currency",
        "close",
        "eps_annual",
        "eps_period_end",
        "eps_filed",
        "eps_form",
        F.datediff("date", "eps_period_end").alias("eps_age_days"),
        F.when(F.col("eps_annual") > 0, F.col("close") / F.col("eps_annual")).alias("pe_ratio"),
        (F.col("eps_annual") / F.col("close")).alias("earnings_yield"),
        "is_filled",
    )


def build_valuation_snapshot(valuation_daily: DataFrame, dim_instrument: DataFrame, lookback_years: int = 5) -> DataFrame:
    """Bieżące P/E spółki na tle jej własnej historii z ostatnich `lookback_years` lat.

    pe_percentile: odsetek dni, w których P/E było <= bieżącemu (0 = najtaniej w historii, 1 = najdrożej).
    """
    last = valuation_daily.groupBy("ticker").agg(F.max("date").alias("as_of_date"))
    current = (
        valuation_daily.join(last, "ticker")
        .filter(F.col("date") == F.col("as_of_date"))
        .select(
            "ticker", "as_of_date", "close", "eps_annual", "eps_period_end",
            F.col("pe_ratio").alias("pe_current"), F.col("earnings_yield").alias("earnings_yield_current"),
        )
    )
    hist = (
        valuation_daily.join(last, "ticker")
        .filter((F.col("date") >= F.add_months(F.col("as_of_date"), -12 * lookback_years)) & F.col("pe_ratio").isNotNull())
        .join(current.select("ticker", "pe_current"), "ticker")
    )
    stats = hist.groupBy("ticker").agg(
        F.percentile_approx("pe_ratio", 0.5).alias("pe_median_hist"),
        F.min("pe_ratio").alias("pe_min_hist"),
        F.max("pe_ratio").alias("pe_max_hist"),
        F.avg(F.when(F.col("pe_ratio") <= F.col("pe_current"), 1.0).otherwise(0.0)).alias("pe_percentile_hist"),
        F.count(F.lit(1)).alias("hist_days"),
    )
    return (
        current.join(stats, "ticker", "left")
        .withColumn("pe_vs_median", F.col("pe_current") / F.col("pe_median_hist") - 1)
        .withColumn("lookback_years", F.lit(lookback_years))
        .join(dim_instrument.select("ticker", "name", "sector"), "ticker", "left")
    )


# --------------------------------------------------------------------------------------
# Portfel modelowy funduszu
# --------------------------------------------------------------------------------------
def portfolio_start_date(prices_daily: DataFrame, weights: dict[str, float], start_date: str):
    """Pierwszy dzień >= start_date, w którym WSZYSTKIE pozycje mają cenę w PLN."""
    px = (
        prices_daily.filter(F.col("ticker").isin(list(weights)))
        .filter((F.col("date") >= F.to_date(F.lit(start_date))) & F.col("close_pln").isNotNull())
    )
    firsts = px.groupBy("ticker").agg(F.min("date").alias("first_date")).collect()
    missing = set(weights) - {r["ticker"] for r in firsts}
    if missing:
        raise ValueError(f"Brak notowań w PLN dla pozycji portfela: {sorted(missing)}")
    return max(r["first_date"] for r in firsts)


def build_portfolio_positions_daily(
    prices_daily: DataFrame, weights: dict[str, float], start_date: str, initial_capital: float
) -> DataFrame:
    """Kup i trzymaj: w dniu startu kapitał dzielimy według wag, liczba jednostek potem stała.

    value_pln_fixed_fx = wartość przy kursie walut zamrożonym na dzień startu,
    fx_effect_pln = value_pln - value_pln_fixed_fx -> ile zarobiliśmy/straciliśmy na samym kursie walut.
    """
    common_start = portfolio_start_date(prices_daily, weights, start_date)
    weight_map = F.create_map(*[x for t, v in weights.items() for x in (F.lit(t), F.lit(float(v)))])
    px = (
        prices_daily.filter(F.col("ticker").isin(list(weights)))
        .withColumn("weight", F.element_at(weight_map, F.col("ticker")))
        .filter(F.col("date") >= F.lit(common_start))
    )
    base = px.filter(F.col("date") == F.lit(common_start)).select(
        "ticker",
        F.col("close_pln").alias("start_close_pln"),
        F.col("fx_rate").alias("start_fx_rate"),
    )
    return (
        px.join(base, "ticker")
        .withColumn("units", F.lit(float(initial_capital)) * F.col("weight") / F.col("start_close_pln"))
        .withColumn("value_pln", F.col("units") * F.col("close_pln"))
        .withColumn("value_pln_fixed_fx", F.col("units") * F.col("close") * F.col("start_fx_rate"))
        .withColumn("fx_effect_pln", F.col("value_pln") - F.col("value_pln_fixed_fx"))
        .select(
            "date", "ticker", "currency", "weight", "units", "close", "fx_rate", "close_pln",
            "value_pln", "value_pln_fixed_fx", "fx_effect_pln",
        )
    )


def build_portfolio_daily(
    positions: DataFrame, initial_capital: float, trading_days: int = 252, rolling_window: int = 30
) -> DataFrame:
    w = Window.orderBy("date")
    w_run = w.rowsBetween(Window.unboundedPreceding, 0)
    w_roll = w.rowsBetween(-(rolling_window - 1), 0)
    daily = positions.groupBy("date").agg(
        F.sum("value_pln").alias("value_pln"),
        F.sum("value_pln_fixed_fx").alias("value_pln_fixed_fx"),
        F.sum("fx_effect_pln").alias("fx_effect_pln"),
        F.count(F.lit(1)).alias("n_positions"),
    )
    return (
        daily.withColumn("daily_return", F.col("value_pln") / F.lag("value_pln").over(w) - 1)
        .withColumn("daily_return_fixed_fx", F.col("value_pln_fixed_fx") / F.lag("value_pln_fixed_fx").over(w) - 1)
        .withColumn("cum_return", F.col("value_pln") / F.lit(float(initial_capital)) - 1)
        .withColumn("cum_return_fixed_fx", F.col("value_pln_fixed_fx") / F.lit(float(initial_capital)) - 1)
        .withColumn("running_max_pln", F.max("value_pln").over(w_run))
        .withColumn("drawdown", F.col("value_pln") / F.col("running_max_pln") - 1)
        .withColumn(
            "rolling_volatility",
            F.when(
                F.count("daily_return").over(w_roll) >= rolling_window,
                F.stddev_samp("daily_return").over(w_roll) * F.lit(math.sqrt(trading_days)),
            ),
        )
    )


# --------------------------------------------------------------------------------------
# Zwrot i ryzyko
# --------------------------------------------------------------------------------------
def series_metrics(
    df: DataFrame, key: str, value_col: str, return_col: str, risk_free: float = 0.0, trading_days: int = 252
) -> DataFrame:
    """Metryki szeregu wartości: łączny zwrot, CAGR, zmienność roczna, zwrot/ryzyko, max drawdown."""
    w_run = Window.partitionBy(key).orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    d = df.withColumn("_runmax", F.max(value_col).over(w_run)).withColumn(
        "_dd", F.col(value_col) / F.col("_runmax") - 1
    )
    agg = d.groupBy(key).agg(
        F.min("date").alias("start_date"),
        F.max("date").alias("end_date"),
        F.min_by(value_col, "date").alias("start_value"),
        F.max_by(value_col, "date").alias("end_value"),
        F.stddev_samp(return_col).alias("_daily_vol"),
        F.min("_dd").alias("max_drawdown"),
        F.count(F.lit(1)).alias("n_days"),
    )
    years = F.datediff("end_date", "start_date") / F.lit(365.25)
    return (
        agg.withColumn("years", years)
        .withColumn("total_return", F.col("end_value") / F.col("start_value") - 1)
        .withColumn(
            "cagr",
            F.when(F.col("years") > 0, F.pow(F.col("end_value") / F.col("start_value"), 1 / F.col("years")) - 1),
        )
        .withColumn("volatility", F.col("_daily_vol") * F.lit(math.sqrt(trading_days)))
        .withColumn(
            "return_to_risk",
            F.when(F.col("volatility") > 0, (F.col("cagr") - F.lit(risk_free)) / F.col("volatility")),
        )
        .drop("_daily_vol")
    )


_METRIC_COLS = ["total_return", "cagr", "volatility", "return_to_risk", "max_drawdown"]


def build_risk_return(
    prices_daily: DataFrame,
    portfolio_daily: DataFrame,
    dim_instrument: DataFrame,
    portfolio_name: str,
    risk_free: float = 0.0,
    trading_days: int = 252,
) -> DataFrame:
    """Porównanie spółek, indeksów i portfela w tym samym okresie (od startu portfela).

    *_pln   – wynik inwestora rozliczającego się w PLN (z efektem kursowym),
    *_local – wynik w walucie notowania (dla portfela: przy kursach zamrożonych na dzień startu),
    fx_effect_cagr = cagr_pln - cagr_local (punkty procentowe rocznie).
    """
    start = portfolio_daily.agg(F.min("date")).first()[0]
    px = prices_daily.filter(F.col("date") >= F.lit(start))

    def _both(df, key, v_pln, r_pln, v_loc, r_loc):
        pln = series_metrics(df, key, v_pln, r_pln, risk_free, trading_days)
        loc = series_metrics(df, key, v_loc, r_loc, risk_free, trading_days)
        pln = pln.select(key, "start_date", "end_date", "years", "n_days", *[F.col(c).alias(f"{c}_pln") for c in _METRIC_COLS])
        loc = loc.select(key, *[F.col(c).alias(f"{c}_local") for c in _METRIC_COLS])
        return pln.join(loc, key)

    inst = _both(px, "ticker", "close_pln", "daily_return_pln", "close", "daily_return_local").join(
        dim_instrument.select("ticker", "name", "instrument_type", "currency", "sector", "in_portfolio"), "ticker"
    )
    port_src = portfolio_daily.withColumn("ticker", F.lit(PORTFOLIO_KEY))
    port = _both(port_src, "ticker", "value_pln", "daily_return", "value_pln_fixed_fx", "daily_return_fixed_fx").select(
        "*",
        F.lit(portfolio_name).alias("name"),
        F.lit("portfolio").alias("instrument_type"),
        F.lit("PLN").alias("currency"),
        F.lit(None).cast("string").alias("sector"),
        F.lit(True).alias("in_portfolio"),
    )
    out = inst.unionByName(port).withColumn("fx_effect_cagr", F.col("cagr_pln") - F.col("cagr_local"))
    rank_w = Window.partitionBy("instrument_type").orderBy(F.col("return_to_risk_pln").desc_nulls_last())
    return out.withColumn("rank_return_to_risk", F.dense_rank().over(rank_w))
