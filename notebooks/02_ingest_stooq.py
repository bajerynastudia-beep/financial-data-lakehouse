# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Pozyskanie: notowania Stooq → Bronze
# MAGIC Źródło: Stooq, dzienne notowania (CSV) spółek i indeksów z `config/instruments.yml`.
# MAGIC - wymaga klucza API (sekret `stooq_api_key` w scope `fin-lakehouse`),
# MAGIC - **tryb incremental**: od ostatniej daty w Bronze minus 7 dni (łapiemy korekty notowań),
# MAGIC - odpowiedź HTML zamiast CSV albo komunikat o limicie → czytelny błąd dla danego tickera;
# MAGIC   pozostałe tickery są pobierane dalej, a krok kończy się błędem na końcu (job ponowi próbę),
# MAGIC - surowe CSV w Volume, wiersze dopisywane do `fin_bronze.stooq_prices`.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

res = run_step("ingest_stooq", lambda: pipeline.ingest_stooq(spark, cfg, RUN_ID, MODE, dbutils))

# COMMAND ----------

bronze_table = cfg.table("bronze", pipeline.BRONZE["prices"])
display(spark.sql(f"""
    SELECT ticker, COUNT(*) AS wiersze, MIN(date) AS od, MAX(date) AS do, MAX(_ingest_ts) AS ostatnie_pobranie
    FROM {bronze_table} GROUP BY ticker ORDER BY ticker
"""))
