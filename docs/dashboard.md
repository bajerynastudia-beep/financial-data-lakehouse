# Dashboard (tydzień 3) – jak zbudować w Databricks AI/BI

Wymaganie projektu: interaktywny interfejs korzystający z danych z potoku, odpowiadający na co najmniej
dwa pytania z karty projektu. Proponowany układ – **do decyzji i wykonania przez zespół**.

## Kroki
1. Uruchom potok (job albo notatniki `01`–`06`), sprawdź wyniki w `07_analysis`.
2. W Databricks: **New → Dashboard**.
3. Zakładka **Data**: dodaj zapytania z `sql/dashboard_queries.sql` – każde jako osobny dataset.
4. Zakładka **Canvas**: dodaj wizualizacje (tabela poniżej) i filtry.
5. **Publish**. Eksport do repozytorium: menu ⋮ → *Export* → plik `.lvdash.json` zapisz w `dashboards/`
   (dzięki temu oceniający zaimportuje dashboard, a zmiany są w historii Git).

## Proponowane strony i wizualizacje

| Strona | Wizualizacja | Dataset | Pytanie |
|---|---|---|---|
| Screening | wykres punktowy: zmienność (X) vs CAGR w PLN (Y), kolor = rynek | P1 | P1 |
| Screening | tabela rankingu zwrot/ryzyko | P1 | P1 |
| Wycena | słupki: percentyl historyczny P/E (0–100%) dla spółek z USA | P2a | P2 |
| Wycena | linia: P/E w czasie, filtr = spółka | P2b | P2 |
| Waluty | słupki: CAGR w USD vs w PLN | P3a | P3 |
| Waluty | linia: wartość portfela z kursem rzeczywistym i stałym + USD/PLN | P3b | P3 |
| Ryzyko | obszar: drawdown portfela; linia: zmienność krocząca | P4 | P4 |
| Jakość danych | tabela wyników testów + licznik „ostatnia aktualizacja” | DQ, aktualność | – |

Filtry: zakres dat, rynek (GPW/USA), spółka. Na każdej stronie zastrzeżenie:
*„Analiza danych historycznych na potrzeby projektu – nie stanowi rekomendacji inwestycyjnej.”*

Odświeżanie: dashboard czyta tabele Gold, więc pokazuje wynik ostatniego poprawnego uruchomienia potoku.
Można dodać harmonogram odświeżania w ustawieniach dashboardu po godzinie uruchomienia joba.
