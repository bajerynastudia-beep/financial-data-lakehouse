# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Testy jakości danych (Silver) – bramka przed warstwą Gold
# MAGIC 15 automatycznych testów, 7 rodzajów reguł: kompletność, unikalność, zakres, dozwolone wartości,
# MAGIC integralność referencyjna, aktualność oraz reguły dziedzinowe (spójność OHLC, skoki cen, podejrzenie splitu).
# MAGIC
# MAGIC - wyniki zapisywane do `fin_ops.dq_results` (historia wszystkich uruchomień),
# MAGIC - test o istotności **error**, który nie przejdzie, **przerywa potok** – zadanie w jobie kończy się błędem,
# MAGIC   a warstwa Gold nie jest budowana ze złych danych,
# MAGIC - test **warn** jest raportowany (status WARN), ale nie zatrzymuje potoku.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

results = pipeline.silver_quality_checks(spark, cfg)
run_step("quality_silver", lambda: pipeline.run_quality(spark, cfg, RUN_ID, results))

# COMMAND ----------

display(spark.table(DQ_TABLE).filter(f"run_id = '{RUN_ID}'").orderBy("status", "table_name"))
