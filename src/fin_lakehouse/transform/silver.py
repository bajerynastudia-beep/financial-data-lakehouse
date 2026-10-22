"""Bronze -> Silver: typowanie, deduplikacja, odrzucanie błędnych rekordów do kwarantanny.

Zasady warstwy Silver:
- typy danych są jawne (daty, liczby); błędny tekst NIE przerywa potoku (try_cast -> NULL),
  tylko trafia do kwarantanny z opisem przyczyny,
- jeden wiersz na klucz biznesowy (ostatnio pobrana wersja wygrywa),
- zapis przez MERGE (idempotentny – ponowne uruchomienie nie tworzy duplikatów).
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

# Klucze biznesowe tabel Silver (używane w deduplikacji, MERGE i testach jakości)
FX_KEYS = ["currency", "date"]
PRICE_KEYS = ["ticker", "date"]
EPS_KEYS = ["cik", "period_start", "period_end", "accn"]

ANNUAL_FORMS = ["10-K", "10-K/A"]


def try_cast(col_name: str, type_name: str) -> Column:
    """Rzutowanie odporne na błędne wartości (NULL zamiast wyjątku w trybie ANSI)."""
    return F.expr(f"try_cast(`{col_name}` AS {type_name})")


def add_reject_reason(df: DataFrame, rules: list[tuple[str, Column]]) -> DataFrame:
    """Dodaje kolumnę _reject_reason = nazwa PIERWSZEJ naruszonej reguły (albo NULL).

    rules: lista (nazwa_reguły, warunek_oznaczający_BŁĄD). Warunki powinny jawnie obsługiwać NULL.
    """
    reason = F.lit(None).cast("string")
    for name, is_bad in reversed(rules):
        reason = F.when(is_bad, F.lit(name)).otherwise(reason)
    return df.withColumn("_reject_reason", reason)


TECH_COLUMNS = {"_ingest_ts", "_source_file", "_run_id"}


def raw_json(bronze: DataFrame) -> Column:
    """Oryginalny rekord Bronze jako JSON – trafia do kwarantanny bez zmian."""
    return F.to_json(F.struct(*[F.col(c) for c in bronze.columns if c not in TECH_COLUMNS]))


def split_valid(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Rozdziela rekordy poprawne i odrzucone (po add_reject_reason)."""
    valid = df.filter(F.col("_reject_reason").isNull()).drop("_reject_reason", "_raw_json")
    rejected = df.filter(F.col("_reject_reason").isNotNull())
    return valid, rejected


def dedupe_latest(df: DataFrame, keys: list[str], order_col: str = "_ingest_ts") -> DataFrame:
    """Zostawia jeden wiersz na klucz – najnowszy według order_col."""
    w = Window.partitionBy(*keys).orderBy(F.col(order_col).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")


# --------------------------------------------------------------------------------------
# Kursy walut NBP
# --------------------------------------------------------------------------------------
def clean_fx(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    df = bronze.select(
        F.upper(F.trim(F.col("currency_code"))).alias("currency"),
        try_cast("effective_date", "DATE").alias("date"),
        try_cast("mid", "DOUBLE").alias("rate_mid"),
        F.col("table_no"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
        raw_json(bronze).alias("_raw_json"),
    )
    df = add_reject_reason(
        df,
        [
            ("missing_currency", F.col("currency").isNull() | (F.col("currency") == "")),
            ("invalid_date", F.col("date").isNull()),
            ("invalid_rate", F.col("rate_mid").isNull()),
            ("non_positive_rate", F.col("rate_mid") <= 0),
        ],
    )
    valid, rejected = split_valid(df)
    return dedupe_latest(valid, FX_KEYS), rejected


# --------------------------------------------------------------------------------------
# Notowania (Stooq)
# --------------------------------------------------------------------------------------
def clean_prices(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    df = bronze.select(
        F.lower(F.trim(F.col("ticker"))).alias("ticker"),
        try_cast("date", "DATE").alias("date"),
        try_cast("open", "DOUBLE").alias("open"),
        try_cast("high", "DOUBLE").alias("high"),
        try_cast("low", "DOUBLE").alias("low"),
        try_cast("close", "DOUBLE").alias("close"),
        try_cast("volume", "DOUBLE").alias("volume"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
        raw_json(bronze).alias("_raw_json"),
    )
    df = add_reject_reason(
        df,
        [
            ("missing_ticker", F.col("ticker").isNull() | (F.col("ticker") == "")),
            ("invalid_date", F.col("date").isNull()),
            ("invalid_close", F.col("close").isNull()),
            ("non_positive_close", F.col("close") <= 0),
        ],
    )
    valid, rejected = split_valid(df)
    return dedupe_latest(valid, PRICE_KEYS), rejected


# --------------------------------------------------------------------------------------
# Zysk na akcję (SEC EDGAR)
# --------------------------------------------------------------------------------------
def clean_eps(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    df = bronze.select(
        try_cast("cik", "INT").alias("cik"),
        F.col("entity_name"),
        try_cast("period_start", "DATE").alias("period_start"),
        try_cast("period_end", "DATE").alias("period_end"),
        try_cast("val", "DOUBLE").alias("eps"),
        F.col("accn"),
        try_cast("fy", "INT").alias("fiscal_year"),
        F.col("fp").alias("fiscal_period"),
        F.col("form"),
        try_cast("filed", "DATE").alias("filed"),
        F.col("frame"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
        raw_json(bronze).alias("_raw_json"),
    )
    df = df.withColumn("duration_days", F.datediff("period_end", "period_start"))
    # Okres roczny: ok. 1 rok (52/53 tygodnie) i raport roczny 10-K.
    df = df.withColumn(
        "is_annual",
        F.coalesce(
            F.col("duration_days").between(350, 380) & F.col("form").isin(ANNUAL_FORMS),
            F.lit(False),
        ),
    )
    df = add_reject_reason(
        df,
        [
            ("missing_key", F.col("cik").isNull() | F.col("period_end").isNull() | F.col("accn").isNull()),
            ("invalid_filed_date", F.col("filed").isNull()),
            ("invalid_eps", F.col("eps").isNull()),
        ],
    )
    valid, rejected = split_valid(df)
    return dedupe_latest(valid, EPS_KEYS), rejected


def to_quarantine(rejected: DataFrame, source_table: str) -> DataFrame:
    """Ujednolica odrzucone rekordy do jednej tabeli kwarantanny (treść jako JSON)."""
    return rejected.select(
        F.lit(source_table).alias("source_table"),
        F.col("_reject_reason").alias("reject_reason"),
        F.col("_raw_json").alias("record_json"),
        F.col("_source_file").alias("source_file"),
        F.col("_ingest_ts").alias("ingest_ts"),
        F.current_timestamp().alias("quarantined_at"),
    )
