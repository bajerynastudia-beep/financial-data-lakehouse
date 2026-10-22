# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Pozyskanie: zysk na akcję (SEC EDGAR) → Bronze
# MAGIC Źródło: SEC EDGAR XBRL *company facts* – oficjalne, bezpłatne dane ze sprawozdań spółek z USA.
# MAGIC Pobieramy miarę `us-gaap:EarningsPerShareDiluted` (rozwodniony zysk na akcję), potrzebną do wskaźnika P/E.
# MAGIC - SEC wymaga nagłówka User-Agent z nazwą i e-mailem (sekret `sec_user_agent`) i max 10 zapytań/s,
# MAGIC - SEC zwraca zawsze pełny stan danych spółki; w trybie incremental pobieramy go najwyżej raz dziennie,
# MAGIC - surowy JSON w Volume, fakty EPS dopisywane do `fin_bronze.sec_eps_facts`.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

res = run_step("ingest_sec", lambda: pipeline.ingest_sec(spark, cfg, RUN_ID, MODE, dbutils))

# COMMAND ----------

bronze_table = cfg.table("bronze", pipeline.BRONZE["eps"])
display(spark.sql(f"""
    SELECT entity_name, cik, form, COUNT(*) AS fakty, MAX(filed) AS ostatni_raport, MAX(_ingest_ts) AS ostatnie_pobranie
    FROM {bronze_table} GROUP BY entity_name, cik, form ORDER BY entity_name, form
"""))
