# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Silver → Gold: model analityczny dla zespołu inwestycyjnego
# MAGIC Pełna przebudowa tabel Gold z danych Silver (deterministyczna – ten sam wynik przy każdym uruchomieniu):
# MAGIC
# MAGIC | Tabela | Do czego służy |
# MAGIC |---|---|
# MAGIC | `dim_instrument`, `dim_date` | wymiary: spółki/indeksy, kalendarz |
# MAGIC | `fact_fx_daily`, `fact_prices_daily` | kursy NBP i ceny w walucie notowania oraz w PLN |
# MAGIC | `fact_valuation_daily`, `valuation_snapshot` | P/E spółek z USA w czasie i na tle własnej historii |
# MAGIC | `portfolio_positions_daily`, `portfolio_daily` | portfel modelowy: wartość, efekt kursowy, obsunięcia |
# MAGIC | `risk_return` | stopa zwrotu, ryzyko i zwrot/ryzyko – spółki, indeksy, portfel |
# MAGIC
# MAGIC Na końcu testy spójności modelu (zapisywane do `fin_ops.dq_results`).

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

gold_checks = []


def _build():
    res, checks = pipeline.build_gold(spark, cfg)
    gold_checks.extend(checks)
    return res


run_step("build_gold", _build)

# COMMAND ----------

run_step("quality_gold", lambda: pipeline.run_quality(spark, cfg, RUN_ID, gold_checks))

# COMMAND ----------

display(spark.table(cfg.table("gold", "risk_return")).orderBy("instrument_type", "rank_return_to_risk"))
