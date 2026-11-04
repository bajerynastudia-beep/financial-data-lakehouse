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

## Tydzień 3 (plan)
- Job w Databricks z harmonogramem i powiadomieniem e-mail o błędzie; obserwacja kilku uruchomień przyrostowych.
- Dashboard AI/BI (decyzja D-12) odpowiadający na pytania P1–P4 ([docs/dashboard.md](docs/dashboard.md)), eksport do repozytorium.

## Tydzień 4 (plan)
- Test uruchomienia według README na czystym koncie / schemacie.
- Uzupełnienie dokumentacji (fragmenty „do uzupełnienia”), podsumowanie, prezentacja i demonstracja na żywo.

## 30.10.2026 – zmiana dostawcy notowań (realizacja)
- Poprzedni endpoint Stooq nie działał: HTML zamiast CSV oraz „Odmowa dostępu” w przeglądarce.
- Dodano FMP jako dostawcę JSON EOD; przerobiono `02_ingest_fmp.py`, `pipeline.py`, `databricks.yml` i testy.
- Zakres bieżący: pięć spółek USA, portfel 5 × 20%, NBP USD/PLN + SEC EPS.
- Konieczne do zrobienia: podanie bezpiecznych sekretów `fmp_api_key`, `sec_user_agent` w Databricks;
  test `00_setup`, pełne ładowanie, testy Silver/Gold, uruchomienie i eksport dashboardu AI/BI.
- Historia od 2023 r. zależy od uprawnień bezpłatnego planu FMP; brak potwierdzenia pokrycia z API.
- Zmiana kodu wykonana przy wsparciu ChatGPT; do zweryfikowania przez autorkę projektu w Databricks.

## 30.10–03.11.2026 – rzeczywiste uruchomienie i dashboard AI/BI
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

## 03.11.2026 – przygotowanie automatyzacji Databricks
- Potwierdzono definicję 7-zadaniowego joba w `databricks.yml`: pobieranie NBP/FMP/SEC, Silver, bramka DQ i Gold.
- Dodano [docs/automatyzacja.md](docs/automatyzacja.md) z krokami wdrożenia przez Databricks CLI na Windows.
- Harmonogram 07:30 w dni robocze jest celowo `PAUSED`, aż do udanego testowego uruchomienia.
- **Do potwierdzenia w środowisku:** `bundle validate`, `bundle deploy`, pierwsze `bundle run`, ewentualna aktywacja harmonogramu.

## 04.11.2026 – udany test joba
- Wykonano lokalnie `databricks bundle validate` (Validation OK) i `bundle deploy` (1 job, 58 plików).
- Uruchomiono `fin_lakehouse_pipeline` z `mode=incremental`; Databricks potwierdził `Succeeded` po 3 min 43 s (18:39–18:43 UTC / 19:39–19:43 Warszawa). Na screenie zadania `quality_silver` oraz `gold` są zielone.
- W repo przełączono harmonogram na `UNPAUSED` (dni robocze o 07:30, Europe/Warsaw).
- **Do aktywacji w Databricks:** lokalne `git pull --ff-only` + ponowny `databricks bundle deploy`, następnie kontrola zakładki Schedules & Triggers. Brak jeszcze potwierdzenia działania cyklicznego.
