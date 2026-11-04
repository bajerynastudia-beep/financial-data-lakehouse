# Migracja z Stooq do Financial Modeling Prep (FMP)

## Co zostało zmienione
- Dostawca cen: `FMP`, endpoint `https://financialmodelingprep.com/stable/historical-price-eod/full` (JSON).
- Nowy notebook: `notebooks/02_ingest_fmp.py`; nowy kod: `src/fin_lakehouse/sources/fmp.py`.
- Tabela Bronze z notowaniami: `workspace.fin_bronze.fmp_prices` (zamiast `stooq_prices`).
- Warstwa Silver: `workspace.fin_silver.prices`; Gold: `workspace.fin_gold.*`.
- Portfel 5 spółek USA (AAPL, MSFT, KO, JPM, XOM), wagi po 20%. Brak GPW i indeksów w aktualnym zakresie.
- Parametr `history_start = 2023-01-01` określa zapytanie, **nie gwarantuje dostępu** do całego okresu.

## Po pobraniu zmian Git → Pull w Databricks
1. Nie kasuj wcześniejszych danych z `workspace.bronze`, `workspace.silver` ani `workspace.gold`.
   Nowy projekt korzysta z osobnych schematów `workspace.fin_*`.
2. W Databricks skonfiguruj secret scope `fin-lakehouse` (CLI):
   ```sh
   databricks secrets create-scope fin-lakehouse
   databricks secrets put-secret fin-lakehouse fmp_api_key
   databricks secrets put-secret fin-lakehouse sec_user_agent
   databricks secrets list-secrets fin-lakehouse
   ```
   W przypadku istniejącego scope pomiń pierwszą komendę.
   `fmp_api_key`: klucz z konta FMP. `sec_user_agent`: identyfikator projektu + prawdziwy e-mail kontaktowy.
   Nie wklejaj sekretów w notebookach ani do repozytorium.
3. Otwórz `notebooks/00_setup.py` i uruchom **Run all**. W tabeli NBP, FMP, SEC muszą mieć status **OK**.
4. Sprawdź dostęp do historii: uruchom `notebooks/02_ingest_fmp.py` w trybie `mode=full`,
   a następnie odczytaj z tabeli Bronze MIN(date), MAX(date), COUNT(*) per ticker.
   Gdy FMP zwróci błąd planu lub brak danych, notebook zakończy się błędem zamiast fałszywego sukcesu.
5. Jeśli FMP udostępnia potrzebne dane: uruchom `01_ingest_nbp`, `03_ingest_sec`, `04_silver`,
   `05_quality_silver`, `06_gold`, a potem `07_analysis`; wszystkie w tym samym Git folderze.
   Uwaga: w `mode=full` wymagane są odpowiednie dane historyczne dla wszystkich 5 spółek.
6. Zbuduj interaktywny dashboard według `docs/dashboard.md`, korzystając z `sql/dashboard_queries.sql`.

## Typowe problemy
- `ConfigError: Brak sekretu fmp_api_key`: skonfiguruj sekret w scope `fin-lakehouse`.
- `FmpError: brak notowań` lub komunikat o planie: darmowy plan może nie obsługiwać żądanego symbolu/okresu.
  Nie wpisuj ręcznie fikcyjnych notowań. Zweryfikuj swoje uprawnienia i ogranicz daty tylko po świadomej decyzji.
- `ConfigError: Brak sekretu sec_user_agent`: dodaj identyfikator z działającym e-mailem.
- `SourceError` (HTTP): sprawdź dostęp sieciowy z Databricks Free Edition.
- Błąd w `05_quality_silver`: odczytaj historię w `workspace.fin_ops.dq_results`.

## Stan walidacji
- Kod zaktualizowano w repozytorium GitHub, testy jednostkowe uruchamia GitHub Actions.
- Potwierdzono pobranie 961 notowań FMP na każdą z 5 spółek, od 03.01.2023 do 30.10.2026 (łącznie 4805 rekordów) w uruchomieniu Full.
- Wykonano pełne ładowanie i testowy job incremental w Databricks (04.11.2026: `Succeeded`, 3 min 43 s).
- Dashboard AI/BI z 5 wykresami i 2 filtrami wyeksportowano do `dashboards/financial-data-lakehouse.lvdash.json`; publikacja nie została osobno potwierdzona.
- Testy Silver+Gold: 22, w tym 21 PASS, 1 WARN (6 naruszeń reguły ostrzegawczej), 0 FAIL.
