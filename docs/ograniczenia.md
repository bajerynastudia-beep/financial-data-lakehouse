# Ograniczenia rozwiązania i kierunki rozwoju

## Ograniczenia

**Dane i dziedzina**
- Projekt obejmuje teraz wyłącznie pięć spółek USA (bez GPW oraz indeksów); efekt kursowy dla PLN jest nadal liczony.
- P/E z rocznego EPS (raport 10-K): po zamknięciu roku wskaźnik może opierać się na zysku sprzed ponad roku;
  nie uwzględnia wyników kwartalnych (TTM) ani zdarzeń jednorazowych.
- Model P/E korzysta z rocznego EPS SEC; dla spółek po splicie historyczne P/E może być
  niespójne (sygnalizuje to test `eps_restatement_split_suspect`).
- Lista spółek wybrana dzisiaj – wyniki historyczne są zawyżone przez **efekt przetrwania** (spółki, które
  zbankrutowały lub wypadły z indeksów, nie są analizowane).
- Ceny z FMP mogą podlegać korektom; nie weryfikujemy ich z drugim źródłem.
- Portfel modelowy nie uwzględnia dywidend (o ile nie są w cenach skorygowanych), kosztów transakcyjnych, podatków
  ani rebalancingu; kurs NBP to kurs referencyjny, a nie kurs, po którym fundusz wymienia walutę.
- Dzienna częstotliwość danych – brak danych śróddziennych.

**Technika i środowisko**
- Databricks Free Edition: tylko serverless, ograniczony dostęp do internetu (może wymagać weryfikacji konta),
  limity zużycia, brak gwarancji dostępności.
- FMP wymaga klucza API; limit zapytań, dostępne symbole i maksymalny zasięg historii zależą od planu. Pełna historia od 2023 r. NIE jest gwarantowana.
- Gold jest przebudowywany w całości przy każdym uruchomieniu – wystarczające dla obecnego wolumenu.
- Watermark Silver opiera się o `_ingest_ts`: jeśli cała nowa partia trafi do kwarantanny, przy kolejnym
  uruchomieniu zostanie przetworzona ponownie (duplikaty w kwarantannie, nie w Silver).
- Testy jednostkowe transformacji działają na lokalnym Sparku (GitHub Actions); integracja z Delta/Unity Catalog
  jest weryfikowana uruchomieniem w Databricks.

## Kierunki rozwoju
- P/E TTM z danych kwartalnych i dodatkowe wskaźniki: P/BV, EV/EBITDA, dywidenda, ROE (te same dane SEC).
- Źródło wyników dla spółek z GPW (np. licencjonowany dostawca) i P/E dla GPW.
- Analiza scenariuszy: wpływ zmiany USD/PLN o ±10% na wartość portfela; symulacja zabezpieczenia walutowego.
- Benchmark portfela (WIG20 / S&P 500 w PLN) i miary względne (beta, tracking error).
- Alerty: e-mail, gdy spółka spadnie do najniższych 10% historycznego P/E albo drawdown portfela przekroczy limit.
- Kontrakty danych i *lineage* w Unity Catalog; osobne środowiska dev/prod w bundle.

- Databricks nie został jeszcze przetestowany end-to-end po migracji. Bez poprawnego pełnego ładowania Gold i dashboard mogą pozostawać puste.
