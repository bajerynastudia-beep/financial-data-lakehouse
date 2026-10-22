# Databricks notebook source
# MAGIC %md
# MAGIC # Wspólny kod startowy
# MAGIC Dołączany na początku każdego notatnika potoku przez `%run ./_common`.
# MAGIC - dodaje katalog `src/` repozytorium do ścieżki Pythona (logika potoku jest w pakiecie `fin_lakehouse`),
# MAGIC - wczytuje i waliduje konfigurację z `config/*.yml`,
# MAGIC - tworzy widżety `mode` (incremental / full) i `run_id` (wypełniany automatycznie przez job),
# MAGIC - udostępnia `run_step(...)`, który zapisuje przebieg każdego kroku do `fin_ops.pipeline_runs`.
# MAGIC
# MAGIC Po zmianie kodu w `src/` uruchom `dbutils.library.restartPython()` albo odłącz i podłącz notatnik,
# MAGIC żeby Python wczytał nową wersję modułów.

# COMMAND ----------

import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fin_lakehouse import lakehouse_io as io  # noqa: E402
from fin_lakehouse import pipeline  # noqa: E402
from fin_lakehouse.config import load_config  # noqa: E402

dbutils.widgets.dropdown("mode", "incremental", ["incremental", "full"], "Tryb ładowania")
dbutils.widgets.text("run_id", "", "Id uruchomienia (wypełnia job)")

MODE = dbutils.widgets.get("mode")
RUN_ID = io.new_run_id(dbutils.widgets.get("run_id"))
cfg = load_config(REPO_ROOT)
pipeline.setup(spark, cfg)  # CREATE ... IF NOT EXISTS – bezpieczne przy każdym uruchomieniu
RUNS_TABLE = cfg.table("ops", pipeline.OPS["runs"])
DQ_TABLE = cfg.table("ops", pipeline.OPS["dq"])

print(f"Repozytorium: {REPO_ROOT}\nKatalog: {cfg.catalog} | tryb: {MODE} | run_id: {RUN_ID}")


def run_step(step, fn):
    """Uruchamia krok potoku i zapisuje jego wynik (SUCCESS/FAILED) do rejestru uruchomień.
    Błąd jest zapisywany, a potem zgłaszany dalej – zadanie w jobie kończy się na czerwono."""
    started = datetime.now(timezone.utc)
    res = None
    try:
        res = fn()
        if getattr(res, "errors", None):
            res.raise_if_errors()
    except Exception as exc:
        io.log_step(spark, RUNS_TABLE, RUN_ID, step, "FAILED", getattr(res, "rows", None), str(exc), started)
        raise
    details = json.dumps(getattr(res, "details", {}) or {}, default=str, ensure_ascii=False)
    io.log_step(spark, RUNS_TABLE, RUN_ID, step, "SUCCESS", getattr(res, "rows", None), details, started)
    print(f"[{step}] OK – rekordy: {getattr(res, 'rows', '-')}, pliki: {getattr(res, 'files', '-')}, {details}")
    return res
