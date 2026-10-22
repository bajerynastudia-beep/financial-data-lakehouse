# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Przygotowanie środowiska i test źródeł danych
# MAGIC 1. Tworzy schematy `fin_bronze`, `fin_silver`, `fin_gold`, `fin_ops` oraz Volume `fin_bronze.raw` na surowe pliki.
# MAGIC 2. Sprawdza, czy z tego workspace działają wszystkie źródła danych i sekrety (NBP, Stooq, SEC EDGAR).
# MAGIC
# MAGIC Uruchom ten notatnik raz po podłączeniu repozytorium. Jeśli któreś źródło ma status **BŁĄD**,
# MAGIC komunikat mówi, co poprawić (najczęściej: brak sekretu albo brak dostępu do internetu w Free Edition).

# COMMAND ----------

# MAGIC %pip install -q -r ../requirements.txt

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

for layer in ("bronze", "silver", "gold", "ops"):
    print("schemat:", cfg.schema(layer))
print("volume :", cfg.raw_volume_path)

# COMMAND ----------

status = pipeline.check_sources(cfg, dbutils)
display(spark.createDataFrame(status))
if any(s["status"] != "OK" for s in status):
    print(
        "Co najmniej jedno źródło nie działa. Sprawdź:\n"
        "- sekrety: README.md, sekcja 'Sekrety' (scope 'fin-lakehouse'),\n"
        "- dostęp do internetu: Databricks Free Edition ogranicza ruch wychodzący; "
        "weryfikacja konta przez LinkedIn odblokowuje dostęp."
    )
