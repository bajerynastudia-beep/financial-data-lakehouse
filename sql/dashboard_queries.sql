-- Zapytania dla dashboardu AI/BI (każde = osobny "dataset" w dashboardzie).
-- Katalog/schemat: workspace.fin_gold (zmień, jeśli w config/settings.yml jest inny).
-- Zastrzeżenie na dashboardzie: analiza danych historycznych, nie stanowi rekomendacji inwestycyjnej.

-- P1. Zwrot w relacji do ryzyka (wykres punktowy: X = zmienność, Y = CAGR, etykieta = spółka)
SELECT name                       AS spolka,
       instrument_type            AS typ,
       currency                   AS waluta,
       sector                     AS sektor,
       cagr_pln                   AS cagr_pln,
       volatility_pln             AS zmiennosc_pln,
       return_to_risk_pln         AS zwrot_do_ryzyka,
       max_drawdown_pln           AS max_obsuniecie,
       rank_return_to_risk        AS ranking
FROM workspace.fin_gold.risk_return;

-- P2a. Bieżąca wycena na tle historii (tabela / wykres słupkowy percentyla)
SELECT name                  AS spolka,
       sector                AS sektor,
       as_of_date            AS na_dzien,
       pe_current            AS pe_biezace,
       pe_median_hist        AS pe_mediana_5l,
       pe_min_hist           AS pe_min_5l,
       pe_max_hist           AS pe_max_5l,
       pe_percentile_hist    AS percentyl_historyczny,
       pe_vs_median          AS odchylenie_od_mediany,
       earnings_yield_current AS stopa_zysku
FROM workspace.fin_gold.valuation_snapshot;

-- P2b. P/E w czasie (wykres liniowy, seria = spółka)
SELECT v.date, i.name AS spolka, v.pe_ratio, v.eps_annual, v.eps_period_end
FROM workspace.fin_gold.fact_valuation_daily v
JOIN workspace.fin_gold.dim_instrument i USING (ticker)
WHERE v.pe_ratio IS NOT NULL;

-- P3a. Efekt kursowy w zwrocie (wykres słupkowy: CAGR w walucie vs w PLN)
SELECT name AS spolka, currency AS waluta, cagr_local, cagr_pln, fx_effect_cagr
FROM workspace.fin_gold.risk_return
WHERE currency <> 'PLN' OR instrument_type = 'portfolio';

-- P3b. Wartość portfela z kursem rzeczywistym vs zamrożonym (wykres liniowy) + kurs USD/PLN
SELECT p.date, p.value_pln, p.value_pln_fixed_fx, p.fx_effect_pln, fx.rate_mid AS usd_pln
FROM workspace.fin_gold.portfolio_daily p
LEFT JOIN workspace.fin_gold.fact_fx_daily fx ON fx.date = p.date AND fx.currency = 'USD';

-- P4. Obsunięcia kapitału i zmienność krocząca portfela (wykres liniowy/obszarowy)
SELECT date, value_pln, cum_return, drawdown, rolling_volatility
FROM workspace.fin_gold.portfolio_daily;

-- Jakość danych: wyniki testów z ostatniego uruchomienia (tabela na dashboardzie)
SELECT check_name, table_name, rule_type, severity, status, failed_count, details, checked_at
FROM workspace.fin_ops.dq_results
WHERE run_id = (SELECT run_id FROM workspace.fin_ops.dq_results ORDER BY checked_at DESC LIMIT 1)
ORDER BY CASE status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, table_name;

-- Aktualność danych: ostatnie udane uruchomienie każdego kroku
SELECT step, MAX(finished_at) AS ostatni_sukces
FROM workspace.fin_ops.pipeline_runs
WHERE status = 'SUCCESS'
GROUP BY step;
