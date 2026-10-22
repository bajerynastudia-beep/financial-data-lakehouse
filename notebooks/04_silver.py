# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Bronze → Silver: oczyszczanie, typowanie, deduplikacja
# MAGIC - typy jawne (daty, liczby); wartości, których nie da się odczytać, nie przerywają potoku, tylko trafiają
# MAGIC   do **kwarantanny** `fin_silver.quarantine` z przyczyną i oryginalnym rekordem,
# MAGIC - jeden wiersz na klucz biznesowy (najnowsze pobranie wygrywa),
# MAGIC - zapis **MERGE** (upsert) → ponowne uruchomienie nie tworzy duplikatów,
# MAGIC - **tryb incremental**: przetwarzane są tylko rekordy Bronze nowsze niż ostatnio przetworzone.

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

res = run_step("build_silver", lambda: pipeline.build_silver(spark, cfg, RUN_ID, MODE))

# COMMAND ----------

for name in ("fx", "prices", "eps"):
    t = cfg.table("silver", pipeline.SILVER[name])
    print(t, spark.table(t).count(), "wierszy")

quarantine = cfg.table("silver", pipeline.SILVER["quarantine"])
if spark.catalog.tableExists(quarantine):
    display(spark.sql(f"""
        SELECT source_table, reject_reason, COUNT(*) AS rekordy, MAX(quarantined_at) AS ostatnio
        FROM {quarantine} GROUP BY source_table, reject_reason ORDER BY rekordy DESC
    """))

# COMMAND ----------

# MAGIC %md
# MAGIC Historia zmian tabeli Delta (time travel) – każdy MERGE to nowa wersja tabeli:

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY {cfg.table('silver', pipeline.SILVER['prices'])}").select(
    "version", "timestamp", "operation", "operationMetrics"))
