# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Pozyskanie: kursy walut NBP → Bronze
# MAGIC Źródło: API NBP, tabela A (kursy średnie), waluty z `config/settings.yml` (USD, EUR).
# MAGIC - **tryb incremental**: pobiera tylko dni po ostatniej dacie zapisanej w Bronze,
# MAGIC - **tryb full**: pobiera całą historię od `history_start`,
# MAGIC - zakres dzielony na kawałki ≤ 90 dni (limit API: 93 dni), błędy przejściowe ponawiane,
# MAGIC   odpowiedź 404 = brak notowań (weekend/święto), a nie błąd,
# MAGIC - surowy JSON zapisywany bez zmian w Volume, wiersze dopisywane do `fin_bronze.nbp_fx_rates`.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

res = run_step("ingest_nbp", lambda: pipeline.ingest_nbp(spark, cfg, RUN_ID, MODE))

# COMMAND ----------

bronze_table = cfg.table("bronze", pipeline.BRONZE["fx"])
display(spark.sql(f"""
    SELECT currency_code, COUNT(*) AS wiersze, MIN(effective_date) AS od, MAX(effective_date) AS do,
           MAX(_ingest_ts) AS ostatnie_pobranie
    FROM {bronze_table} GROUP BY currency_code ORDER BY currency_code
"""))
