"""Zapis i odczyt w Databricks: Unity Catalog, tabele Delta, Volumes, rejestr uruchomień."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterable

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

TECH_COLUMNS = ["_source_file"]


def new_run_id(given: str | None = None) -> str:
    """Identyfikator uruchomienia: z joba ({{job.run_id}}) albo 'manual-<czas>' przy ręcznym starcie."""
    return given.strip() if given and given.strip() else "manual-" + datetime.now().strftime("%Y%m%dT%H%M%S")


def save_raw(volume_path: str, source: str, file_name: str, text: str, ingest_date: str) -> str:
    """Zapisuje surową odpowiedź źródła BEZ ZMIAN do Volume. Zwraca ścieżkę pliku."""
    directory = f"{volume_path}/{source}/ingest_date={ingest_date}"
    os.makedirs(directory, exist_ok=True)
    path = f"{directory}/{file_name}"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def rows_to_bronze(spark: SparkSession, rows: list[dict[str, Any]], columns: list[str], run_id: str) -> DataFrame:
    """Wiersze ze źródła -> DataFrame Bronze: wszystkie kolumny jako tekst + metadane techniczne."""
    all_cols = columns + TECH_COLUMNS
    schema = T.StructType([T.StructField(c, T.StringType(), True) for c in all_cols])
    data = [tuple(None if r.get(c) is None else str(r.get(c)) for c in all_cols) for r in rows]
    return (
        spark.createDataFrame(data, schema)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_run_id", F.lit(run_id))
    )


def table_exists(spark: SparkSession, name: str) -> bool:
    return spark.catalog.tableExists(name)


def append(df: DataFrame, table: str) -> None:
    df.write.mode("append").option("mergeSchema", "true").saveAsTable(table)


def overwrite(df: DataFrame, table: str) -> None:
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)


def merge_upsert(spark: SparkSession, df: DataFrame, table: str, keys: list[str]) -> None:
    """Idempotentny zapis do Silver: wstaw nowe klucze, zaktualizuj istniejące nowszą wersją.

    Porównanie kluczy jest odporne na NULL (<=>). Rekord jest nadpisywany tylko wtedy, gdy
    pochodzi z późniejszego pobrania – ponowne uruchomienie na tych samych danych nic nie zmienia.
    """
    if not table_exists(spark, table):
        df.write.saveAsTable(table)
        return
    from delta.tables import DeltaTable  # dostępne w Databricks

    cond = " AND ".join(f"t.`{k}` <=> s.`{k}`" for k in keys)
    (
        DeltaTable.forName(spark, table)
        .alias("t")
        .merge(df.alias("s"), cond)
        .whenMatchedUpdateAll(condition="s._ingest_ts > t._ingest_ts")
        .whenNotMatchedInsertAll()
        .execute()
    )


def max_by_group(spark: SparkSession, table: str, group_col: str, value_col: str) -> dict[str, Any]:
    """Znacznik przyrostu (watermark): największa wartość value_col w każdej grupie."""
    if not table_exists(spark, table):
        return {}
    rows = spark.table(table).groupBy(group_col).agg(F.max(value_col).alias("m")).collect()
    return {r[group_col]: r["m"] for r in rows}


def max_value(spark: SparkSession, table: str, col: str) -> Any:
    if not table_exists(spark, table):
        return None
    return spark.table(table).agg(F.max(col)).first()[0]


def log_step(
    spark: SparkSession,
    table: str,
    run_id: str,
    step: str,
    status: str,
    rows: int | None = None,
    message: str = "",
    started_at: datetime | None = None,
) -> None:
    """Rejestr przebiegu potoku (fin_ops.pipeline_runs) – co, kiedy, ile rekordów, z jakim skutkiem."""
    schema = T.StructType(
        [
            T.StructField("run_id", T.StringType()),
            T.StructField("step", T.StringType()),
            T.StructField("status", T.StringType()),
            T.StructField("rows_processed", T.LongType()),
            T.StructField("message", T.StringType()),
            T.StructField("started_at", T.TimestampType()),
            T.StructField("finished_at", T.TimestampType()),
        ]
    )
    now = datetime.now(timezone.utc)
    df = spark.createDataFrame(
        [(run_id, step, status, None if rows is None else int(rows), message[:4000], started_at or now, now)], schema
    )
    append(df, table)


def write_dq_results(spark: SparkSession, table: str, results: Iterable[Any], run_id: str) -> DataFrame:
    schema = T.StructType(
        [
            T.StructField("run_id", T.StringType()),
            T.StructField("check_name", T.StringType()),
            T.StructField("table_name", T.StringType()),
            T.StructField("rule_type", T.StringType()),
            T.StructField("severity", T.StringType()),
            T.StructField("status", T.StringType()),
            T.StructField("failed_count", T.LongType()),
            T.StructField("details", T.StringType()),
            T.StructField("checked_at", T.TimestampType()),
        ]
    )
    data = []
    for r in results:
        row = r.as_row(run_id)
        data.append(tuple(row[f.name] if f.name != "details" else (row["details"] or "")[:4000] for f in schema.fields))
    df = spark.createDataFrame(data, schema)
    append(df, table)
    return df
