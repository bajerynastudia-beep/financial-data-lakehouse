# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Odpowiedzi na pytania biznesowe (podgląd wyników z warstwy Gold)
# MAGIC Notatnik do szybkiego sprawdzenia wyników i do prezentacji. Te same zapytania są w `sql/dashboard_queries.sql`
# MAGIC i służą jako źródło danych dashboardu AI/BI.
# MAGIC
# MAGIC > Analiza danych historycznych na potrzeby projektu – nie jest rekomendacją inwestycyjną.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

G = cfg.schema("gold")

# COMMAND ----------

# MAGIC %md
# MAGIC ## P1. Które spółki dawały najlepszą stopę zwrotu w relacji do ryzyka (w PLN)?

# COMMAND ----------

display(spark.sql(f"""
    SELECT rank_return_to_risk AS miejsce, name AS spolka, currency AS waluta,
           ROUND(cagr_pln * 100, 1) AS cagr_pln_proc, ROUND(volatility_pln * 100, 1) AS zmiennosc_proc,
           ROUND(return_to_risk_pln, 2) AS zwrot_do_ryzyka, ROUND(max_drawdown_pln * 100, 1) AS max_obsuniecie_proc
    FROM {G}.risk_return
    WHERE instrument_type IN ('stock', 'portfolio')
    ORDER BY instrument_type DESC, rank_return_to_risk
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## P2. Czy spółki z USA są dziś drogie czy tanie względem własnej historii (P/E)?

# COMMAND ----------

display(spark.sql(f"""
    SELECT name AS spolka, as_of_date AS na_dzien, ROUND(pe_current, 1) AS pe_biezace,
           ROUND(pe_median_hist, 1) AS pe_mediana_5l, ROUND(pe_percentile_hist * 100) AS percentyl_proc,
           ROUND(earnings_yield_current * 100, 2) AS stopa_zysku_proc, eps_period_end AS eps_za_okres
    FROM {G}.valuation_snapshot ORDER BY pe_percentile_hist
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT v.date, i.name AS spolka, v.pe_ratio
    FROM {G}.fact_valuation_daily v JOIN {G}.dim_instrument i USING (ticker)
    WHERE v.pe_ratio IS NOT NULL ORDER BY v.date
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## P3. Jak kurs USD/PLN wpływał na wynik inwestycji w spółki z USA?

# COMMAND ----------

display(spark.sql(f"""
    SELECT name AS spolka, ROUND(cagr_local * 100, 1) AS cagr_w_usd_proc, ROUND(cagr_pln * 100, 1) AS cagr_w_pln_proc,
           ROUND(fx_effect_cagr * 100, 1) AS efekt_kursowy_pp_rocznie
    FROM {G}.risk_return WHERE currency <> 'PLN' OR instrument_type = 'portfolio'
    ORDER BY efekt_kursowy_pp_rocznie
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## P4. Kiedy portfel modelowy miał największe spadki i jak zmieniało się jego ryzyko?

# COMMAND ----------

display(spark.sql(f"""
    SELECT date, value_pln, value_pln_fixed_fx, drawdown, rolling_volatility
    FROM {G}.portfolio_daily ORDER BY date
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT date AS dzien_dna, ROUND(drawdown * 100, 1) AS obsuniecie_proc, ROUND(value_pln) AS wartosc_pln
    FROM {G}.portfolio_daily ORDER BY drawdown LIMIT 10
"""))
