# Postęp prac

## Tydzień 1 (do 14.10.2026)
- Wybór tematu i karta projektu: Data Lakehouse do analizy rentowności i ryzyka portfela inwestycyjnego.
- Utworzenie repozytorium GitHub i struktury katalogów (8.10).
- Konfiguracja Databricks Free Edition; pierwszy notatnik pobierający kursy walut z API NBP
  (praca w workspace Databricks, jeszcze poza repozytorium).

## Tydzień 2 (15.10–22.10.2026)
- Repozytorium podłączone do Databricks jako Git folder (15.10).
- Doprecyzowanie odbiorcy: zespół inwestycyjny funduszu analizujący spółki do inwestycji;
  zakres: spółki z GPW i USA, wskaźnik P/E z danych SEC EDGAR (22.10).
- Z pomocą AI (Claude) przygotowano potok w kodzie (22.10):
  - konfiguracja instrumentów i portfela modelowego bez sekretów,
  - pobieranie: NBP (limit 93 dni, 404 = brak danych), Stooq (klucz API, wykrywanie błędów), SEC EDGAR (EPS),
  - Bronze (surowe pliki + tabele tekstowe), Silver (typy, kwarantanna, deduplikacja, MERGE),
  - Gold: kursy i ceny w PLN, P/E bez look-ahead, portfel modelowy, zwrot/ryzyko,
  - 22 testy jakości danych (bramka przed Gold), testy jednostkowe pytest w GitHub Actions,
  - notatniki 00–07, job jako kod (`databricks.yml`), dokumentacja w `docs/`.
- **Do zrobienia przez zespół w tym tygodniu:** sekrety (klucz Stooq, User-Agent SEC), uruchomienie `00_setup`
  i pierwszego pełnego ładowania w Databricks, weryfikacja wyników w `07_analysis`, przegląd kodu,
  tag `tydzien-2`.
- Decyzje projektowe D-03–D-12 przyjęte zgodnie z zasadą „przy równorzędnych opcjach – rozwiązanie prostsze” (22.10).

## Tydzień 3 (23.10–29.10.2026)
- W repozytorium brak commitów z tego tygodnia.
- Zaplanowane na ten tydzień prace (job z harmonogramem i powiadomieniem, dashboard AI/BI) zrealizowano
  w tygodniu 4, po wymianie źródła notowań (Stooq → FMP, decyzja D-13 z 30.10).

## Tydzień 4 (30.10–05.11.2026)
Podsumowanie tygodnia: wymiana źródła notowań na FMP, pierwsze pełne ładowanie w Databricks, dashboard AI/BI,
job z harmonogramem i alertem, audyt testów jakości, prezentacja na zaliczenie. Szczegóły w kolejności dat:

### 30.10.2026 – zmiana dostawcy notowań (realizacja)
- Poprzedni endpoint Stooq nie działał: HTML zamiast CSV oraz „Odmowa dostępu” w przeglądarce.
- Dodano FMP jako dostawcę JSON EOD; przerobiono `02_ingest_fmp.py`, `pipeline.py`, `databricks.yml` i testy.
- Zakres bieżący: pięć spółek USA, portfel 5 × 20%, NBP USD/PLN + SEC EPS.
- Konieczne do zrobienia: podanie bezpiecznych sekretów `fmp_api_key`, `sec_user_agent` w Databricks;
  test `00_setup`, pełne ładowanie, testy Silver/Gold, uruchomienie i eksport dashboardu AI/BI.
- Historia od 2023 r. zależy od uprawnień bezpłatnego planu FMP; brak potwierdzenia pokrycia z API.
- Zmiana kodu wykonana przy wsparciu ChatGPT; do zweryfikowania przez autorkę projektu w Databricks.

### 30.10–03.11.2026 – rzeczywiste uruchomienie i dashboard AI/BI
- W Databricks utworzono secret scope `fin-lakehouse`; sprawdzono połączenie NBP, FMP i SEC: wszystkie 3 statusy OK.
- Pełne pobranie do Bronze: FMP – 5 × 961 = 4805 notowań (03.01.2023–30.10.2026);
  NBP – USD i EUR po 966 rekordów (łącznie 1932); SEC – dane EPS spółek USA.
- Uruchomiono Silver i 15 automatycznych kontroli jakości (14 PASS, 1 WARN, bez błędów krytycznych);
  Gold oraz analizy P1–P4 zwróciły wyniki finansowe.
- W Databricks utworzono 5 wykresów, 4 KPI oraz filtry spółki i dat; użytkowniczka potwierdziła działanie filtra dat dla 2025.
- Otrzymano i dodano eksport `dashboards/financial-data-lakehouse.lvdash.json` do Git.
- **Pozostałe prace:** weryfikacja publikacji i ponownego importu dashboardu, dodanie zastrzeżenia
  o charakterze edukacyjnym, potwierdzenie szczegółów testów Gold, harmonogram joba,
  tagi tygodniowe, odtworzenie na czystym środowisku i prezentacja.

### 03.11.2026 – przygotowanie automatyzacji Databricks
- Potwierdzono definicję 7-zadaniowego joba w `databricks.yml`: pobieranie NBP/FMP/SEC, Silver, bramka DQ i Gold.
- Dodano [docs/automatyzacja.md](docs/automatyzacja.md) z krokami wdrożenia przez Databricks CLI na Windows.
- Harmonogram 07:30 w dni robocze jest celowo `PAUSED`, aż do udanego testowego uruchomienia.
- **Do potwierdzenia w środowisku:** `bundle validate`, `bundle deploy`, pierwsze `bundle run`, ewentualna aktywacja harmonogramu.

### 04.11.2026 – udany test joba
- Wykonano lokalnie `databricks bundle validate` (Validation OK) i `bundle deploy` (1 job, 58 plików).
- Uruchomiono `fin_lakehouse_pipeline` z `mode=incremental`; Databricks potwierdził `Succeeded` po 3 min 43 s (18:39–18:43 UTC / 19:39–19:43 Warszawa). Na screenie zadania `quality_silver` oraz `gold` są zielone.
- W repo przełączono harmonogram na `UNPAUSED` (dni robocze o 07:30, Europe/Warsaw).
- **Do aktywacji w Databricks:** lokalne `git pull --ff-only` + ponowny `databricks bundle deploy`, następnie kontrola zakładki Schedules & Triggers. Brak jeszcze potwierdzenia działania cyklicznego.

### 04.11.2026 – aktualizacja powiadomień
- Użytkowniczka uruchomiła `databricks bundle deploy -p dbc-8b06d9f3-fe92` po dodaniu konfiguracji alertów.
- Databricks potwierdził `Updated jobs.fin_lakehouse_pipeline`; 2 pliki przesłane, 1 zasób zmieniony, bez błędów wdrożenia.
- Konfiguracja w repo: `email_notifications.on_failure` wykorzystuje `${workspace.current_user.userName}` dla aktualnego użytkownika.
- **Pozostało sprawdzić w Databricks UI:** odbiorcę powiadomień w ustawieniach joba oraz pierwsze faktyczne uruchomienie harmonogramu.

### 04.11.2026 – kontrola alertów w interfejsie
- Użytkowniczka pokazała sekcję `Job notifications` z odbiorcą zaczynającym się od `bajery.na.studia...` i wyzwalaczem `On failure`; na ekranie widać również `Bundle repository URL` wskazujący repozytorium GitHub.
- Potwierdzono, że konfiguracja alertów jest widoczna w UI. Dostarczenie e-maila przy faktycznej awarii nie było testowane.
- Dalsze zadania: sprawdzić 22 kontrole DQ ostatniego uruchomienia, wykonanie harmonogramu 05.11.2026 i kompletność projektu przed oddaniem.

### 04.11.2026 – audyt kontroli jakości Silver i Gold
- Na podstawie wyniku zapytania do `workspace.fin_ops.dq_results` dla najnowszego `run_id`: dokładnie 22 testy.
- `PASS` / `error`: 15 testów, 0 naruszeń; `PASS` / `warn`: 6 testów, 0 naruszeń; `WARN` / `warn`: 1 test, 6 naruszeń.
- **Łącznie: 21 PASS, 1 WARN, 0 FAIL**, bez zablokowania potoku. Nazwa reguły ostrzegawczej wymaga potwierdzenia w wynikach szczegółowych; wcześniejsze uruchomienie zgłaszało `eps_restatement_split_suspect`.
- Pozostaje sprawdzenie świeżości Gold, faktycznego pierwszego uruchomienia planowego i kompletności dashboardu przed oddaniem.

### 04.11.2026 – identyfikacja jedynego ostrzeżenia jakości
- Reguła: `eps_restatement_split_suspect`, tabela: `workspace.fin_silver.eps_facts`, 6 przypadków, ważność `warn`.
- Widoczne przykłady: CIK 21344 (Coca-Cola, 2010 i 2011, EPS ~×2), CIK 320193 (Apple, 2012 i 2013, EPS ~×7; 2018, EPS ~×4). Szczegóły testu pokazują tylko próbkę 5 z 6 przypadków.
- Test analizuje roczne dodatnie EPS o tym samym `cik`, `period_start`, `period_end` w różnych zgłoszeniach SEC i sprawdza stosunek maksimum do minimum; nie rozstrzyga przyczyny bez analizy filingów.
- Wyniki historycznej wyceny P/E mogą być podatne na niespójności skorygowanych/niekorygowanych splitów. **Nie potwierdzono jeszcze, czy roczne EPS z ostrzeżonych okresów są użyte w przedziale dashboardu 2023–2026.** Potrzebna kontrola `eps_period_end` w tabeli `workspace.fin_gold.fact_valuation_daily`.


### 04.11.2026 – kontrola aktualności Gold
- Na podstawie wyników SQL: `fact_prices_daily` 4820 rekordów (od 03.01.2023 do 04.11.2026), `fact_valuation_daily` również 4820, `fact_fx_daily` 2892, `portfolio_daily` 964.
- Wspólny kalendarz 964 sesji: 5 instrumentów × 964 = 4820; waluty USD/EUR/PLN × 964 = 2892. Warstwa Gold rozciąga serie FX i wycen na kalendarz sesji.
- W porównaniu z poprzednim snapshotem 4805 notowań FMP pojawiło się 15 dodatkowych rekordów dziennych (trzy sesje × pięć spółek).
- **Uwaga do dalszego sprawdzenia:** wyniki z datą 04.11.2026 zostały pokazane przed zamknięciem sesji USA; należy upewnić się, że FMP zwraca finalny EOD lub aktualizuje tymczasowe notowania po sesji. Późniejsze uruchomienie 05.11 o 07:30 powinno już przypadać po zamknięciu sesji USA z 04.11.
- Sprawdzono 4 widoczne spółki w kontroli EPS: AAPL, JPM, KO, MSFT mają 0 dni, w których wycena od 2023 korzysta z EPS 2018 lub starszego. Wynik XOM pozostaje do potwierdzenia.

### 04.11.2026 – kontrola dat notowań wszystkich instrumentów
- W `workspace.fin_gold.fact_prices_daily` wszystkie 5 tickerów (AAPL, JPM, KO, MSFT, XOM) mają zarówno `MAX(date)`, jak i `MAX(CASE WHEN NOT is_filled THEN date END)` równe `2026-11-04`.
- Agregacja `COUNT_IF(is_filled)` pokazała puste wartości na zrzucie ekranu, nie potwierdzono jeszcze liczby historycznych uzupełnień (należy użyć `SUM(CASE WHEN is_filled THEN 1 ELSE 0 END)`).
- Data 04.11 nie jest dowodem uzyskania finalnych cen EOD przed zamknięciem sesji w USA. Po sesji warto porównać dane źródłowe FMP / ponowne uruchomienie incremental.

### 04.11.2026 – zakończenie kontroli wykorzystania historycznych EPS
- Dodatkowe zapytanie dla XOM: najstarszy używany `eps_period_end` = `2021-12-31`; `dni_z_historycznym_eps` (okresy do 2018-12-31 włącznie) = 0.
- Łącznie wszystkie 5 spółek (AAPL, MSFT, KO, JPM, XOM) ma 0 dni wycen od 2023 r. opartych na EPS z roku 2018 lub starszych.
- Wcześniejsze ostrzeżenie `eps_restatement_split_suspect` (6 przypadków w SEC) pozostaje ważną informacją o danych historycznych, ale wskazane podejrzane lata 2010–2018 nie są wykorzystywane w badanym okresie 2023–2026.
- Nie oznacza to pełnego audytu wartości P/E; do potwierdzenia pozostała publikacja dashboardu oraz pierwsze planowe uruchomienie joba.

### 04.11.2026 – potwierdzenie publikacji dashboardu
- Użytkowniczka pokazała opublikowany widok Databricks AI/BI Dashboard: dostępny przycisk `Edit draft`, widoczne cztery KPI, filtry spółki i zakresu dat, wykresy CAGR i P/E.
- Bieżący widok przedstawiał wartość portfela ~191,16 tys. PLN, CAGR ~18,4%, łączną stopę zwrotu ~91,16% i maks. drawdown -19,36%.
- Nazwa obiektu dashboardu w nagłówku nadal brzmiała `New Dashboard 2026-11-02 19:29:40`, chociaż nagłówek strony ma docelowy tytuł. Do poprawy nazwa obiektu.
- W prawym górnym rogu był wskaźnik `23h ago` oraz opcja `Schedule`; nie potwierdzono jeszcze osobnego harmonogramu odświeżania dashboardu po jobie.
- Należy dodać zastrzeżenie o edukacyjnym charakterze analizy, po zmianach ponownie opublikować i wyeksportować nowszą definicję `.lvdash.json` do GitHub.

### 04.11.2026 – harmonogram odświeżania dashboardu
- Użytkowniczka pokazała sekcję Databricks Dashboard `Schedules` z wpisem `At 08:00 (UTC+1)`, trybem `Refresh` i jednym odbiorcą.
- Poprzedni job aktualizacji tabel Gold jest zaplanowany na dni robocze 07:30 Europe/Warsaw. Dashboard zaplanowano na 08:00 czasu UTC+1 (zrzut z listopada).
- Do potwierdzenia: częstotliwość odświeżania dashboardu, obsługa zmiany czasu i pierwsze wykonanie według harmonogramu. Harmonogram dashboardu nie oczekuje automatycznie na zakończenie joba.
- Ostatnie kroki przed oddaniem: dodać zastrzeżenie edukacyjne, poprawić nazwę obiektu dashboardu, opublikować aktualną wersję i ponownie wyeksportować plik `.lvdash.json`.

### 04.11.2026 – końcowy eksport dashboardu AI/BI
- Użytkowniczka przekazała nowy eksport po zmianie nazwy obiektu dashboardu. Zastąpiono nim `dashboards/financial-data-lakehouse.lvdash.json` w głównej gałęzi GitHub (commit `66046228595339823d0d5c661489e42be1574010`).
- Ostateczny plik ma 6 datasetów SQL, 5 wykresów, 4 KPI, 2 filtry i nagłówek. Zbędny dataset z poprzedniego eksportu został usunięty.
- Na prośbę autorki dashboard pozostaje bez dodatkowego tekstu o rekomendacjach inwestycyjnych. Ograniczenia metodologiczne są opisane w `docs/dashboard.md`.
- Pozostało potwierdzić pierwsze wykonanie harmonogramu i opcjonalnie import eksportu w czystym środowisku.

### 04.11.2026 – przygotowanie prezentacji na zaliczenie
- Przygotowano 15-slajdową prezentację akademicką w formatach PPTX (z notatkami prowadzącej) i PDF, obejmującą problem, źródła, architekturę, transformacje, 9 tabel Gold, jakość, automatykę i pytania biznesowe P1–P4.
- Utworzono scenariusz wypowiedzi, plan demonstracji na żywo na 120 sekund, FAQ i checklistę przygotowań: [docs/prezentacja_na_zaliczenie.md](docs/prezentacja_na_zaliczenie.md).
- W prezentacji użyto rzeczywistych wizualizacji z dashboardu i wyników Gold według stanu 04.11.2026.
- Uporządkowano starsze stwierdzenia o wstrzymanym harmonogramie i nieprzetestowanym potoku w README, docs/architektura.md i docs/ograniczenia.md.
- **Nadal do weryfikacji w praktyce:** pierwsze zaplanowane uruchomienie joba, częstotliwość i strefa czasowa harmonogramu dashboardu oraz ewentualny import eksportu na czystym koncie.

### 05.11.2026 – przegląd względem wymagań projektu
- Przegląd repozytorium względem dokumentu z wymaganiami (wymagania minimalne, rezultaty do oddania) wykonany z pomocą Claude.
- Kod: wartości klucza API maskowane w komunikatach błędów HTTP (klucz FMP nie trafia do logów joba ani do
  `fin_ops.pipeline_runs`), usunięte pozostałości po Stooq; 2 nowe testy jednostkowe.
- Dokumentacja: instrukcje CLI bez prywatnego profilu, aktualne statusy decyzji D-02, D-07, D-13, słownik bez indeksów,
  opis bramek jakości Silver/Gold, pełniejsza sekcja „Wykorzystanie AI” w README.
- `PROGRESS.md` uporządkowany w czterech sekcjach tygodniowych; dodane tagi `tydzien-1` … `tydzien-4`.
- Do sprawdzenia w Databricks: pierwsze planowe uruchomienie joba (05.11, 07:30) i odświeżenie dashboardu o 08:00.
