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
  potwierdzenie decyzji w `docs/decyzje.md`, tag `tydzien-2`.

## Tydzień 3 (plan)
- Job w Databricks z harmonogramem i powiadomieniem e-mail o błędzie; obserwacja kilku uruchomień przyrostowych.
- Dashboard AI/BI odpowiadający na pytania P1–P4 ([docs/dashboard.md](docs/dashboard.md)), eksport do repozytorium.
- Decyzja D-12 (dashboard AI/BI vs Streamlit).

## Tydzień 4 (plan)
- Test uruchomienia według README na czystym koncie / schemacie.
- Uzupełnienie dokumentacji (fragmenty „do uzupełnienia”), podsumowanie, prezentacja i demonstracja na żywo.
