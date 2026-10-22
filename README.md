# Financial Data Lakehouse – screening spółek dla zespołu inwestycyjnego funduszu

![testy](https://github.com/bajerynastudia-beep/financial-data-lakehouse/actions/workflows/tests.yml/badge.svg)

Projekt zaliczeniowy z Inżynierii danych. Potok danych w **Databricks + Delta Lake**, który codziennie pobiera
kursy walut (NBP), notowania spółek z GPW i USA (Stooq) oraz wyniki finansowe spółek z USA (SEC EDGAR),
oczyszcza je, kontroluje jakość i buduje model analityczny dla dashboardu.

> Analiza danych historycznych na potrzeby projektu – nie stanowi rekomendacji inwestycyjnej.

## Cel i odbiorca

**Odbiorca:** zespół inwestycyjny (analitycy, zarządzający) polskiego funduszu, który rozlicza się w PLN
i inwestuje w spółki z GPW i USA. **Proces:** cykliczny przegląd listy obserwacyjnej i portfela modelowego.

| # | Pytanie biznesowe |
|---|---|
| P1 | Które spółki dawały najlepszą stopę zwrotu w relacji do ryzyka, licząc w PLN? |
| P2 | Czy spółki z USA są dziś wyceniane (P/E) drogo czy tanio względem własnej historii? |
| P3 | Jak kurs USD/PLN wpływał na wynik inwestycji w spółki z USA? |
| P4 | Kiedy portfel modelowy notował największe spadki i jak zmieniało się jego ryzyko? |

Szczegóły (4 perspektywy): [docs/kontekst_i_perspektywy.md](docs/kontekst_i_perspektywy.md).

## Architektura w skrócie

```
NBP (JSON) ─┐                 fin_bronze            fin_silver                     fin_gold
Stooq (CSV) ├─> Volume raw ─> tabele tekstowe ─> typy, MERGE, kwarantanna ─> [testy jakości] ─> model ─> dashboard
SEC (JSON) ─┘                                                                   │
                                                              fin_ops: dq_results, pipeline_runs
```

Diagram i opis: [docs/architektura.md](docs/architektura.md) · słownik danych: [docs/slownik_danych.md](docs/slownik_danych.md) ·
decyzje: [docs/decyzje.md](docs/decyzje.md) · ograniczenia: [docs/ograniczenia.md](docs/ograniczenia.md).

## Struktura repozytorium

```
config/                  konfiguracja bez sekretów
  settings.yml           katalog, schematy, źródła, progi testów jakości
  instruments.yml        spółki i indeksy (ticker Stooq, waluta, CIK w SEC)
  portfolio.yml          portfel modelowy (wagi, data startu, kapitał)
src/fin_lakehouse/       logika potoku (pakiet Pythona)
  sources/               pobieranie: nbp.py, stooq.py, sec.py
  transform/             silver.py (Bronze->Silver), gold.py (model analityczny)
  quality/checks.py      reguły jakości danych
  pipeline.py            kroki potoku wywoływane z notatników
  lakehouse_io.py        zapis do Delta/Volume, MERGE, rejestr uruchomień
  http_client.py         ponawianie zapytań, obsługa błędów
  config.py              wczytanie i walidacja konfiguracji, sekrety
notebooks/               notatniki Databricks (format źródłowy .py)
  00_setup … 06_gold     kolejne kroki potoku
  07_analysis            odpowiedzi na pytania biznesowe
sql/dashboard_queries.sql  zapytania dla dashboardu
tests/                   testy jednostkowe (pytest) + syntetyczne próbki odpowiedzi źródeł
databricks.yml           job potoku jako kod (Databricks Asset Bundle)
.github/workflows/       automatyczne testy przy każdym pushu
docs/                    dokumentacja projektu
PROGRESS.md              postęp tydzień po tygodniu
```

## Instalacja i uruchomienie krok po kroku

### 1. Konto i repozytorium
1. Załóż bezpłatne konto **Databricks Free Edition**: https://www.databricks.com/learn/free-edition
2. Jeśli w kroku 3 źródła zwrócą błąd sieci: Free Edition ogranicza ruch wychodzący – zweryfikuj konto przez
   LinkedIn (Settings → weryfikacja), co odblokowuje dostęp do internetu.
3. W Databricks: **Workspace → Create → Git folder**, adres: `https://github.com/bajerynastudia-beep/financial-data-lakehouse`.

### 2. Sekrety (nie trafiają do repozytorium)
Potrzebne dwa sekrety w scope `fin-lakehouse`:

| Klucz | Wartość | Skąd |
|---|---|---|
| `stooq_api_key` | klucz API Stooq | https://stooq.com/q/d/?s=spy.us&get_apikey |
| `sec_user_agent` | nazwa i e-mail, np. `Projekt ID jan.kowalski@example.com` | wymóg SEC EDGAR |

Za pomocą Databricks CLI (na swoim komputerze; instalacja: https://docs.databricks.com/dev-tools/cli/install –
np. Windows: `winget install Databricks.DatabricksCLI`, macOS: `brew tap databricks/tap && brew install databricks`):
```bash
databricks auth login --host https://<twoj-workspace>.cloud.databricks.com
databricks secrets create-scope fin-lakehouse
databricks secrets put-secret fin-lakehouse stooq_api_key      # wklej klucz
databricks secrets put-secret fin-lakehouse sec_user_agent     # wklej nazwę i e-mail
```
Poza Databricks (np. lokalnie) sekrety można podać jako zmienne środowiskowe – wzór w `.env.example`.

### 3. Przygotowanie i test źródeł
Otwórz `notebooks/00_setup` i uruchom (**Run all**). Notatnik tworzy schematy i Volume, a tabela na końcu
pokazuje status każdego źródła (NBP, Stooq, SEC). Wszystkie muszą mieć status **OK**.

### 4. Pierwsze (pełne) ładowanie
**Opcja A – notatniki:** uruchom kolejno `01_ingest_nbp`, `02_ingest_stooq`, `03_ingest_sec`, `04_silver`,
`05_quality_silver`, `06_gold` z widżetem `mode = full` (pierwsze ładowanie pobiera historię od 2019 r.).

**Opcja B – job jako kod (Databricks CLI):**
```bash
databricks bundle deploy
databricks bundle run fin_lakehouse_pipeline --params mode=full
```
**Opcja C – job w interfejsie:** Jobs & Pipelines → Create job → zadania jak w `databricks.yml`
(setup → 3× ingest → silver → quality_silver → gold), parametry joba `mode=incremental`, `run_id={{job.run_id}}`.

Kolejne uruchomienia: `mode = incremental` (domyślnie) – pobierane są tylko nowe dane.
Harmonogram joba (dni robocze 7:30) jest w bundle wstrzymany – włącz go w ustawieniach joba.

### 5. Wyniki i aplikacja
- `notebooks/07_analysis` – odpowiedzi na pytania P1–P4,
- dashboard AI/BI – zapytania w `sql/dashboard_queries.sql`, instrukcja w [docs/dashboard.md](docs/dashboard.md).

### 6. Testy automatyczne (lokalnie)
Wymagany Python 3.10+ i Java 17 (dla PySpark):
```bash
pip install -r requirements-dev.txt
pytest -v
```
Te same testy uruchamia GitHub Actions przy każdym pushu (plakietka na górze README).

## Jakość danych
22 automatyczne testy w 7 rodzajach reguł (kompletność, unikalność, zakres, dozwolone wartości, integralność
referencyjna, aktualność, reguły dziedzinowe). Test krytyczny, który nie przejdzie, **zatrzymuje job** przed
warstwą Gold (czerwone zadanie `quality_silver` z opisem błędu); wszystkie wyniki trafiają do `fin_ops.dq_results`.
Pełna lista: [docs/architektura.md](docs/architektura.md#testy-jakości-danych).

## Wykorzystanie AI
Zgodnie z zasadami projektu opisujemy zakres użycia narzędzi AI:
- **ChatGPT** – propozycje tematów projektu i wstępny plan.
- **Claude (Anthropic)** – na podstawie wymagań projektu i decyzji zespołu (temat, odbiorca: fundusz inwestycyjny,
  zakres: GPW + USA, P/E z danych SEC) wygenerował: kod pakietu `src/`, notatniki, testy, konfigurację, definicję
  joba, workflow CI oraz szkice dokumentacji w `docs/`. Commity przygotowane przez AI mają w opisie
  `Co-Authored-By: Claude`.
- **Zespół:** wybór tematu, odbiorcy i źródeł, uruchomienie i weryfikacja potoku w Databricks, przegląd kodu,
  potwierdzenie decyzji w `docs/decyzje.md`, dashboard **[do uzupełnienia przez zespół]**.

Autorzy odpowiadają za całe rozwiązanie; wyniki i kod wygenerowane przez AI weryfikujemy uruchomieniem,
testami i przeglądem.
