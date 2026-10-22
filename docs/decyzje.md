# Rejestr decyzji projektowych

Format: decyzja, rozważane alternatywy, uzasadnienie. Kolumna **Status**: decyzje zaproponowane z pomocą AI
zespół potwierdza (✅) albo zmienia – decyzje projektowe należą do autorów projektu.
22.10.2026 zespół przyjął zasadę: **przy równorzędnych opcjach wybieramy rozwiązanie prostsze** (łatwiejsze
do wyjaśnienia, odtworzenia i utrzymania), a bardziej złożone warianty zapisujemy jako kierunki rozwoju.

| ID | Data | Decyzja | Status |
|---|---|---|---|
| D-01 | 2026-10-08 | Platforma: Databricks Free Edition + Delta Lake | ✅ zespół |
| D-02 | 2026-10-22 | Odbiorca: zespół inwestycyjny funduszu; źródła: GPW + USA, P/E z SEC | ✅ zespół |
| D-03 | 2026-10-22 | Architektura medalionowa + schemat `fin_ops` | ✅ zespół (wariant prostszy) |
| D-04 | 2026-10-22 | Notowania ze Stooq (API z kluczem) | ✅ zespół (wariant prostszy) |
| D-05 | 2026-10-22 | P/E z rocznego EPS z SEC EDGAR, bez look-ahead; spółki bez splitów | ✅ zespół (wariant prostszy) |
| D-06 | 2026-10-22 | Kurs średni NBP z dnia notowania, uzupełnianie ostatnim kursem | ✅ zespół (wariant prostszy) |
| D-07 | 2026-10-22 | Portfel modelowy: kup i trzymaj, równe wagi | ✅ zespół (wariant prostszy) |
| D-08 | 2026-10-22 | Ładowanie: przyrostowe Bronze/Silver, pełna przebudowa Gold | ✅ zespół (wariant prostszy) |
| D-09 | 2026-10-22 | Bronze jako tekst + surowe pliki w Volume | ✅ zespół (wariant prostszy) |
| D-10 | 2026-10-22 | Własny moduł testów jakości w PySpark | ✅ zespół (wariant prostszy) |
| D-11 | 2026-10-22 | Logika w pakiecie `src/`, cienkie notatniki, CI w GitHub Actions | ✅ zespół (wariant prostszy) |
| D-12 | 2026-10-22 | Aplikacja: dashboard AI/BI w Databricks | ✅ zespół (wariant prostszy) |

---

### D-01. Platforma: Databricks Free Edition + Delta Lake
- **Alternatywy:** zestaw lokalny DuckDB + dbt-core + Prefect/Dagster + Streamlit; PostgreSQL w Dockerze.
- **Uzasadnienie:** zajęcia dotyczą Databricks; Delta Lake daje transakcyjny `MERGE` (idempotentny upsert),
  historię wersji tabel (time travel) i katalog z uprawnieniami (Unity Catalog) bez utrzymywania infrastruktury;
  Free Edition jest bezpłatne, więc oceniający może odtworzyć środowisko bez licencji.
- **Koszt decyzji:** zależność od chmury i limitów Free Edition (tylko serverless, ograniczony dostęp do internetu).
  Przy tak małym wolumenie DuckDB byłby wystarczający – wybór uzasadnia cel dydaktyczny i możliwość skalowania (patrz perspektywa techniczna).

### D-03. Architektura medalionowa (Bronze / Silver / Gold) + `fin_ops`
- **Alternatywy:** dwie warstwy (raw + model); jedna baza z widokami.
- **Uzasadnienie:** oddzielenie surowych danych (audyt, ponowne przetworzenie) od oczyszczonych i od modelu
  pod aplikację – wymaganie projektu; `fin_ops` oddziela dane operacyjne (testy, przebiegi) od biznesowych.

### D-04. Źródło notowań: Stooq (CSV przez API z kluczem)
- **Alternatywy:** Yahoo Finance (nieoficjalne API, warunki serwisu nie przewidują automatycznego pobierania,
  częste zmiany); Alpha Vantage (darmowy limit ok. 25 zapytań dziennie – za mało na historię 13 instrumentów);
  archiwum GPW (oficjalne, ale tylko GPW i jeden plik na dzień – ~1800 plików na historię).
- **Uzasadnienie:** jedno źródło dla GPW, USA i indeksów, historia od lat, prosty format CSV, bezpłatny klucz.
- **Ryzyko:** wymagany klucz API (oceniający musi go uzyskać), dzienny limit pobrań, zmiany formatu – obsłużone
  czytelnymi błędami (`StooqError`) i testem połączenia w `00_setup`. Moduł źródła można wymienić bez zmian w Silver/Gold.

### D-05. P/E z rocznego rozwodnionego EPS z SEC EDGAR, bez zaglądania w przyszłość
- **Alternatywy:** P/E TTM z czterech ostatnich kwartałów (wymaga wyliczenia IV kwartału jako rok − 3 kwartały;
  bardziej złożone i podatne na błędy); gotowe bieżące P/E z API (brak historii, limit zapytań);
  scraping serwisów z P/E dla GPW (warunki serwisów, niestabilny HTML).
- **Uzasadnienie:** SEC to oficjalne, bezpłatne źródło z datą złożenia raportu – pozwala liczyć P/E tylko z danych
  znanych w danym dniu. Roczny EPS jest prostszy do wyjaśnienia odbiorcy.
- **Konsekwencje:** P/E tylko dla spółek z USA; wybrano spółki bez splitu akcji od 2019 r. (split zmienia historyczny
  EPS, a ceny są korygowane wstecz) + test jakości „podejrzenie splitu”.

### D-06. Kurs walut: średni kurs NBP z dnia notowania
- **Alternatywy:** kurs z dnia poprzedniego (jak w księgowości podatkowej); kursy rynkowe śróddzienne (płatne).
- **Uzasadnienie:** oficjalny, bezpłatny kurs referencyjny znany analitykom w Polsce. W dni bez publikacji
  używamy ostatniego kursu i oznaczamy to flagą `fx_is_filled`.

### D-07. Portfel modelowy: kup i trzymaj, równe wagi 10%
- **Alternatywy:** rebalancing miesięczny do wag docelowych; wagi według kapitalizacji.
- **Uzasadnienie:** najprostszy do wyjaśnienia i zweryfikowania (test jednostkowy liczy wynik ręcznie);
  pozwala czysto oddzielić efekt kursowy. Wagi i data startu są w `config/portfolio.yml`.

### D-08. Ładowanie przyrostowe w Bronze/Silver, pełna przebudowa Gold
- **Alternatywy:** pełne ładowanie wszystkiego przy każdym uruchomieniu; przyrostowy Gold.
- **Uzasadnienie:** przyrostowe pobieranie oszczędza limity źródeł i czas; `MERGE` w Silver zapewnia
  idempotentność. Gold to kilkadziesiąt tysięcy wierszy – pełna przebudowa jest szybka i zawsze spójna
  (np. po korekcie historycznych cen). Przy 100× większym wolumenie – Gold przyrostowy (perspektywa techniczna).

### D-09. Bronze jako tekst + surowe pliki w Volume
- **Alternatywa:** typowanie już przy pobieraniu.
- **Uzasadnienie:** zmiana formatu źródła nie przerywa pobierania; wszystkie decyzje interpretacyjne są w Silver
  (jedno miejsce); błędne wartości są widoczne w kwarantannie z oryginalną treścią.

### D-10. Własny moduł testów jakości w PySpark
- **Alternatywy:** Great Expectations / Soda (dodatkowe narzędzie i konfiguracja); oczekiwania w Lakeflow
  Declarative Pipelines (wymaga przebudowy potoku na pipeline deklaratywny).
- **Uzasadnienie:** kilkanaście reguł, pełna kontrola nad komunikatami, testowalność w pytest, działa w Free Edition.

### D-11. Logika w pakiecie `src/fin_lakehouse`, notatniki jako cienka warstwa, CI
- **Alternatywa:** cała logika w notatnikach.
- **Uzasadnienie:** kod w modułach można testować automatycznie (GitHub Actions uruchamia pytest z PySpark przy
  każdym pushu), łatwiej go przeglądać w Git; notatniki służą do uruchamiania i prezentacji.

### D-12. Aplikacja: dashboard AI/BI w Databricks
- **Alternatywa:** aplikacja Streamlit jako Databricks App (więcej interakcji, np. analiza scenariuszy kursu USD/PLN).
- **Uzasadnienie:** dashboard czyta tabele Gold bezpośrednio, nie wymaga pisania ani hostowania aplikacji,
  ma filtry i odświeżanie; eksportujemy go do repozytorium jako `.lvdash.json`, więc oceniający może go zaimportować.
  Streamlit – kierunek rozwoju (analiza scenariuszy).
