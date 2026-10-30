# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Pozyskanie: notowania Financial Modeling Prep (FMP) → Bronze
# MAGIC Dane dzienne EOD (JSON) dla spółek z `config/instruments.yml`.
# MAGIC - klucz `fmp_api_key` przechowywany w Databricks secret scope `fin-lakehouse`,
# MAGIC - tryb full pobiera historię od 2023, incremental pobiera nowe dni z 7-dniową nakładką,
# MAGIC - niepoprawny JSON, pusty wynik lub ograniczenie planu powodują czytelny błąd,
# MAGIC - surowe odpowiedzi są w Volume `fmp`, a ceny w `fin_bronze.fmp_prices`.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

res = run_step("ingest_fmp", lambda: pipeline.ingest_fmp(spark, cfg, RUN_ID, MODE, dbutils))

# COMMAND ----------

bronze_table = cfg.table("bronze", pipeline.BRONZE["prices"])
display(spark.sql(f"""
    SELECT ticker, COUNT(*) AS wiersze, MIN(date) AS od, MAX(date) AS do,
           MAX(_ingest_ts) AS ostatnie_pobranie
    FROM {bronze_table} GROUP BY ticker ORDER BY ticker
"""))
