# Automatyzacja Financial Data Lakehouse – Databricks Jobs

## Architektura joba
Definicja infrastruktury jako kod: [`databricks.yml`](../databricks.yml).
Jeden job `fin_lakehouse_pipeline` z 7 zadaniami:
1. `setup` – weryfikacja źródeł NBP/FMP/SEC i przygotowanie schematów;
2. `ingest_nbp`, `ingest_fmp`, `ingest_sec` – trzy niezależne zadania uruchamiane po setup;
3. `silver` – dopiero po zakończeniu wszystkich trzech pobrań;
4. `quality_silver` – błędy krytyczne zatrzymują wykonanie;
5. `gold` – budowa 9 tabel Gold i testy jakości.

Harmonogram kodu: poniedziałek–piątek 07:30, `Europe/Warsaw`,
`0 30 7 ? * MON-FRI`; na początku ustawiony na `PAUSED`.
Tryb codzienny: `incremental`. `max_concurrent_runs: 1`.
Sekrety są odczytywane z już utworzonego scope `fin-lakehouse`,
a nie zapisane w GitHubie.

## Wdrożenie – PowerShell na Windows
Warunki: zainstalowany Git oraz Databricks CLI i wykonane
`databricks auth login --host https://TWOJ-WORKSPACE`.
Użyj istniejącego profilu CLI (przykładowo `dbc-8b06d9f3-fe92`).

```powershell
git --version
databricks -v
cd $HOME
git clone https://github.com/bajerynastudia-beep/financial-data-lakehouse.git
cd .\financial-data-lakehouse
databricks bundle validate -p dbc-8b06d9f3-fe92
databricks bundle deploy -p dbc-8b06d9f3-fe92
databricks bundle run -p dbc-8b06d9f3-fe92 --params mode=incremental fin_lakehouse_pipeline
```

Jeśli katalog już istnieje, zamiast `git clone` wykonaj w nim
`git pull --ff-only`. Jeśli `git --version` nie działa, zainstaluj Git for Windows:
`winget install --id Git.Git -e`, a potem uruchom ponownie PowerShell.

CLI wdraża kopię plików do workspace jako bundle (`dev`).
Nie uruchamia automatycznie harmonogramu, ponieważ `pause_status: PAUSED`.
Databricks Free Edition obsługuje serverless jobs, jednak ma limity wykorzystania.

## Kontrola testowego uruchomienia
1. W `Jobs & Pipelines` znajdź job o nazwie zbliżonej do `[dev ...] fin-lakehouse-pipeline`.
2. Otwórz ostatnie uruchomienie. Wszystkie zadania muszą mieć status `Succeeded`.
3. Zwróć uwagę, że `ingest_*` może pobrać 0 nowych wierszy, jeśli uruchamiasz job drugi raz tego samego dnia.
4. W SQL Editor sprawdź:
   ```sql
   SELECT step, status, finished_at
   FROM workspace.fin_ops.pipeline_runs
   ORDER BY finished_at DESC LIMIT 20;

   SELECT status, severity, COUNT(*) AS checks
   FROM workspace.fin_ops.dq_results
   GROUP BY status, severity;

   SELECT MAX(date) AS ostatnia_sesja FROM workspace.fin_gold.portfolio_daily;
   ```
5. Otwórz dashboard i zweryfikuj aktualność po odświeżeniu datasetów.

## Uruchomienie codziennego harmonogramu
**Dopiero gdy testowa seria zadań zakończy się sukcesem:**
- w `databricks.yml` zmień `pause_status: PAUSED` na `pause_status: UNPAUSED`,
- zapisz i wypchnij zmianę do GitHub,
- w lokalnym klonie `git pull --ff-only`,
- wykonaj `databricks bundle deploy -p dbc-8b06d9f3-fe92`.
- Sprawdź w `Jobs & Pipelines → Schedules & Triggers`, czy harmonogram jest aktywny.

To podejście zachowuje harmonogram w Git jako źródle prawdy. Sama zmiana harmonogramu
wyłącznie w interfejsie Databricks może zostać nadpisana przy kolejnym wdrożeniu bundle.

## Błędy i ograniczenia
- `ConfigError` sekretów: sprawdź scope `fin-lakehouse` i uprawnienia użytkownika uruchamiającego job.
- `FmpError` lub `SourceError`: sprawdź limit API, brak historii, sieć i dane uwierzytelniające.
- `FAILED` na `quality_silver` oznacza bramkę jakości; nie uruchamiaj Gold z niepoprawnymi danymi.
- Po zmianach źródeł w repo ponownie `git pull` i `bundle deploy`: Git folder w UI
  i pliki bundle są dwiema osobnymi kopiami kodu.
- Dashboard nie jest samodzielnie aktualizowany przez definicję joba:
  czyta najnowsze tabele, ale po publikacji może wymagać odświeżenia datasetów
  lub ustawienia osobnego harmonogramu odświeżania.
- Free Edition: ograniczona liczba równoległych zadań, serwerless i limity fair usage.
- Nie deklarujemy jeszcze, że automatyzacja zadziałała: wymaga rzeczywistego `bundle validate`,
  `deploy` i udanego uruchomienia w workspace.
