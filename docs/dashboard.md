# Dashboard Databricks AI/BI – wersja końcowa

Dashboard **Financial Data Lakehouse | Analiza portfela USA** został zbudowany i opublikowany
w Databricks Free Edition. Definicję odtwarzalną z repozytorium zapisano w pliku
[`dashboards/financial-data-lakehouse.lvdash.json`](../dashboards/financial-data-lakehouse.lvdash.json).
Ostatni eksport dostarczono 04.11.2026 i zastąpiono nim poprzednią wersję.

## Zawartość i źródła

W pliku znajduje się jedna strona, 6 datasetów SQL oraz 12 elementów strony:
- 4 liczniki KPI: wartość portfela (PLN), łączny zwrot, CAGR i maksymalne obsunięcie;
- 5 wykresów: CAGR spółek w PLN, bieżące P/E kontra mediana historyczna,
  CAGR w USD kontra PLN, miesięczne minimalne obsunięcie portfela,
  wartość portfela w PLN przy kursie rzeczywistym i stałym;
- 2 interaktywne filtry: pojedyncza spółka (trzy wykresy spółkowe)
  i zakres dat (dwa wykresy czasowe);
- nagłówek z opisem tematu i źródłami FMP, NBP oraz SEC EDGAR.

Definicja korzysta z tabel `workspace.fin_gold.risk_return`,
`workspace.fin_gold.valuation_snapshot` i `workspace.fin_gold.portfolio_daily`.
Wskaźniki KPI dotyczą całego okresu i nie są przeliczane po zmianie filtrów.

## Aktualizacja danych

Job `fin_lakehouse_pipeline` aktualizuje warstwy Bronze → Silver → Gold
w dni robocze o **07:30 Europe/Warsaw**, po udanym teście całości 04.11.2026.
Na opublikowanym dashboardzie ustawiono niezależny harmonogram odświeżania o
**08:00 (UTC+1 widoczne w listopadzie)**, w trybie `Refresh`.
Nadal trzeba potwierdzić częstotliwość i zachowanie tego harmonogramu
po zmianie czasu. Odświeżenie dashboardu nie czeka automatycznie na zakończenie joba.

## Import i odtworzenie

1. Uruchom pipeline, aby utworzyć wszystkie tabele `workspace.fin_gold.*`.
2. W Databricks otwórz **Dashboards** i zaimportuj plik `.lvdash.json`
   zgodnie z dostępnymi opcjami interfejsu.
3. Zweryfikuj uprawnienia do katalogu `workspace` i tabel Gold oraz dostęp do SQL Warehouse.
4. Sprawdź wykresy i filtry; publikację i harmonogram ustaw ponownie w docelowym workspace.

Eksport nie zawiera danych źródłowych ani kluczy do API. Sam zapis pliku
nie potwierdza udanego importu na nowym koncie — ten test wciąż pozostaje do wykonania.

## Ograniczenia analizy

- Wskaźnik P/E wykorzystuje **ostatni dostępny roczny rozwodniony EPS**,
  nie EPS TTM; mediana odnosi się do okresu dostępnych notowań.
- Reguła jakości `eps_restatement_split_suspect` wykryła 6 historycznych
  podejrzanych przypadków EPS. Weryfikacja dla pięciu spółek wykazała, że
  wyceny od 2023 r. nie korzystają z EPS dla okresów kończących się w 2018 r. lub wcześniej.
  Nie zastępuje to pełnej walidacji danych sprawozdawczych.
- Odświeżenie najnowszych dziennych danych w trakcie trwającej sesji giełdowej
  nie przesądza o ich finalności EOD.

Te informacje pozostają w dokumentacji metodologii; dashboard celowo
skupia się na wynikach i interaktywnych analizach.
