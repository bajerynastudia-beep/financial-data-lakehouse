"""Testy jednostkowe modelu Gold (wymagają PySpark)."""

from datetime import date

import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from fin_lakehouse.transform import gold  # noqa: E402

D1, D2, D3, D4 = date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)

INSTRUMENTS = [
    {"ticker": "pko", "name": "PKO", "market": "GPW", "currency": "PLN", "type": "stock"},
    {"ticker": "a.us", "name": "A Corp", "market": "NYSE", "currency": "USD", "type": "stock", "sec_cik": 1},
]
WEIGHTS = {"pko": 0.5, "a.us": 0.5}


def prices_df(spark, rows):
    return spark.createDataFrame(rows, "ticker string, date date, close double, volume double")


def fx_df(spark, rows):
    return spark.createDataFrame(rows, "currency string, date date, rate_mid double")


def eps_df(spark, rows):
    return spark.createDataFrame(
        rows, "cik int, period_end date, filed date, eps double, form string, is_annual boolean"
    )


def test_fx_daily_forward_fills_missing_nbp_day(spark):
    calendar = spark.createDataFrame([(D1,), (D2,), (D3,)], "date date")
    fx = fx_df(spark, [("USD", D1, 4.0), ("USD", D3, 4.2)])
    out = {(r["currency"], r["date"]): r for r in gold.build_fx_daily(fx, calendar).collect()}
    assert out[("USD", D2)]["rate_mid"] == 4.0 and out[("USD", D2)]["fx_is_filled"] is True
    assert out[("USD", D3)]["fx_is_filled"] is False
    assert out[("PLN", D2)]["rate_mid"] == 1.0


def test_prices_daily_converts_to_pln_and_computes_returns(spark):
    dim = gold.build_dim_instrument(spark, INSTRUMENTS, WEIGHTS)
    prices = prices_df(spark, [("a.us", D1, 10.0, 1.0), ("a.us", D2, 11.0, 1.0), ("pko", D1, 40.0, 1.0),
                               ("pko", D2, 40.0, 1.0), ("pko", D3, 44.0, 1.0)])
    fx = gold.build_fx_daily(fx_df(spark, [("USD", D1, 4.0), ("USD", D2, 4.0), ("USD", D3, 5.0)]),
                             gold.trading_calendar(prices))
    out = {(r["ticker"], r["date"]): r for r in gold.build_prices_daily(prices, fx, dim).collect()}
    assert out[("a.us", D2)]["close_pln"] == pytest.approx(44.0)
    assert out[("a.us", D2)]["daily_return_local"] == pytest.approx(0.1)
    # D3: brak sesji w USA -> cena przeniesiona, ale kurs USD zmienił się -> zwrot w PLN != 0
    assert out[("a.us", D3)]["is_filled"] is True
    assert out[("a.us", D3)]["daily_return_local"] == pytest.approx(0.0)
    assert out[("a.us", D3)]["daily_return_pln"] == pytest.approx(55.0 / 44.0 - 1)
    assert out[("pko", D3)]["daily_return_pln"] == pytest.approx(0.1)


def test_valuation_uses_only_reports_known_on_the_day(spark):
    dim = gold.build_dim_instrument(spark, INSTRUMENTS, WEIGHTS)
    prices_daily = spark.createDataFrame(
        [(date(2024, 2, 1), "a.us", "USD", 40.0, False), (date(2024, 2, 13), "a.us", "USD", 40.0, False),
         (date(2024, 2, 13), "pko", "PLN", 40.0, False)],
        "date date, ticker string, currency string, close double, is_filled boolean",
    )
    eps = eps_df(spark, [
        (1, date(2022, 12, 31), date(2023, 2, 10), 2.0, "10-K", True),
        (1, date(2023, 12, 31), date(2024, 2, 12), 4.0, "10-K", True),   # znany dopiero od 12.02.2024
        (1, date(2023, 9, 30), date(2023, 11, 1), 9.0, "10-Q", False),   # kwartalny – pomijany
    ])
    out = {r["date"]: r for r in gold.build_valuation_daily(prices_daily, eps, dim).collect()}
    assert set(out) == {date(2024, 2, 1), date(2024, 2, 13)}  # tylko spółki z SEC (bez pko)
    assert out[date(2024, 2, 1)]["pe_ratio"] == pytest.approx(20.0)
    assert out[date(2024, 2, 13)]["pe_ratio"] == pytest.approx(10.0)
    assert out[date(2024, 2, 13)]["eps_period_end"] == date(2023, 12, 31)


def test_pe_is_null_for_negative_earnings(spark):
    dim = gold.build_dim_instrument(spark, INSTRUMENTS, WEIGHTS)
    prices_daily = spark.createDataFrame([(D2, "a.us", "USD", 10.0, False)],
                                         "date date, ticker string, currency string, close double, is_filled boolean")
    eps = eps_df(spark, [(1, date(2023, 12, 31), D1, -1.0, "10-K", True)])
    row = gold.build_valuation_daily(prices_daily, eps, dim).collect()[0]
    assert row["pe_ratio"] is None and row["earnings_yield"] == pytest.approx(-0.1)


def test_valuation_snapshot_percentile(spark):
    dim = gold.build_dim_instrument(spark, INSTRUMENTS, WEIGHTS)
    val = spark.createDataFrame(
        [(D1, "a.us", 10.0, 1.0, 10.0, 0.1), (D2, "a.us", 30.0, 1.0, 30.0, 0.03), (D3, "a.us", 20.0, 1.0, 20.0, 0.05)],
        "date date, ticker string, close double, eps_annual double, pe_ratio double, earnings_yield double",
    ).withColumn("eps_period_end", F.lit(date(2023, 12, 31)))
    row = gold.build_valuation_snapshot(val, dim).collect()[0]
    assert row["as_of_date"] == D3 and row["pe_current"] == pytest.approx(20.0)
    assert row["pe_percentile_hist"] == pytest.approx(2 / 3)
    assert row["pe_median_hist"] == pytest.approx(20.0)


def _prices_daily_for_portfolio(spark):
    dim = gold.build_dim_instrument(spark, INSTRUMENTS, WEIGHTS)
    prices = prices_df(spark, [
        ("pko", D1, 10.0, 1.0), ("pko", D2, 12.0, 1.0), ("pko", D3, 9.0, 1.0), ("pko", D4, 10.0, 1.0),
        ("a.us", D1, 100.0, 1.0), ("a.us", D2, 100.0, 1.0), ("a.us", D3, 100.0, 1.0), ("a.us", D4, 100.0, 1.0),
    ])
    fx = gold.build_fx_daily(
        fx_df(spark, [("USD", D1, 4.0), ("USD", D2, 4.0), ("USD", D3, 4.0), ("USD", D4, 5.0)]),
        gold.trading_calendar(prices),
    )
    return gold.build_prices_daily(prices, fx, dim), dim


def test_portfolio_buy_and_hold_and_fx_effect(spark):
    prices_daily, _ = _prices_daily_for_portfolio(spark)
    positions = gold.build_portfolio_positions_daily(prices_daily, WEIGHTS, "2024-01-01", 1000.0)
    daily = {r["date"]: r for r in gold.build_portfolio_daily(positions, 1000.0, rolling_window=2).collect()}
    assert daily[D1]["value_pln"] == pytest.approx(1000.0)
    # D2: pko +20% (500 -> 600), a.us bez zmian (500)
    assert daily[D2]["value_pln"] == pytest.approx(1100.0)
    # D3: pko 450 -> portfel 950; drawdown od szczytu 1100
    assert daily[D3]["drawdown"] == pytest.approx(950.0 / 1100.0 - 1)
    # D4: USD 4 -> 5: a.us 625 PLN, z kursem zamrożonym 500 -> efekt kursowy +125
    assert daily[D4]["value_pln"] == pytest.approx(500.0 + 625.0)
    assert daily[D4]["fx_effect_pln"] == pytest.approx(125.0)
    assert daily[D4]["n_positions"] == 2


def test_portfolio_requires_prices_for_all_positions(spark):
    prices_daily, _ = _prices_daily_for_portfolio(spark)
    with pytest.raises(ValueError, match="xyz"):
        gold.build_portfolio_positions_daily(prices_daily, {"pko": 0.5, "xyz": 0.5}, "2024-01-01", 1000.0)


def test_series_metrics_cagr_volatility_drawdown(spark):
    df = spark.createDataFrame(
        [("x", date(2020, 1, 1), 100.0, None), ("x", date(2021, 1, 1), 120.0, 0.2),
         ("x", date(2021, 6, 1), 90.0, -0.25), ("x", date(2022, 1, 1), 121.0, 121 / 90 - 1)],
        "ticker string, date date, value double, ret double",
    )
    m = gold.series_metrics(df, "ticker", "value", "ret", risk_free=0.0, trading_days=252).collect()[0]
    years = 731 / 365.25
    assert m["total_return"] == pytest.approx(0.21)
    assert m["cagr"] == pytest.approx(1.21 ** (1 / years) - 1)
    assert m["max_drawdown"] == pytest.approx(-0.25)
    assert m["return_to_risk"] == pytest.approx(m["cagr"] / m["volatility"])


def test_risk_return_contains_instruments_and_portfolio(spark):
    prices_daily, dim = _prices_daily_for_portfolio(spark)
    positions = gold.build_portfolio_positions_daily(prices_daily, WEIGHTS, "2024-01-01", 1000.0)
    daily = gold.build_portfolio_daily(positions, 1000.0, rolling_window=2)
    rr = {r["ticker"]: r for r in gold.build_risk_return(prices_daily, daily, dim, "Test").collect()}
    assert set(rr) == {"pko", "a.us", gold.PORTFOLIO_KEY}
    # a.us: cena w USD stała, zysk tylko z kursu -> zwrot lokalny 0, w PLN +25%
    assert rr["a.us"]["total_return_local"] == pytest.approx(0.0)
    assert rr["a.us"]["total_return_pln"] == pytest.approx(0.25)
    assert rr[gold.PORTFOLIO_KEY]["total_return_pln"] == pytest.approx(0.125)
