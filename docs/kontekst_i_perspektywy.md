# Kontekst projektu i cztery perspektywy

> Status: szkic przygotowany z pomocą AI na podstawie decyzji zespołu (temat, odbiorca, źródła).
> Fragmenty oznaczone **[do uzupełnienia]** zespół powinien zweryfikować i opisać własnymi słowami.

## Kontekst

**Odbiorca:** zespół inwestycyjny (analitycy akcji i zarządzający) polskiego funduszu inwestycyjnego
(fikcyjnego), który rozlicza się w PLN i inwestuje w spółki notowane na GPW oraz w USA.

**Problem:** analitycy co tydzień ręcznie zbierają notowania, kursy walut i wyniki finansowe spółek
z różnych serwisów do arkuszy. Dane są niespójne (różne kalendarze sesji, waluty, terminy publikacji
raportów), trudno je odtworzyć, a porównania „w PLN” i wskaźniki wyceny są liczone za każdym razem od nowa.

**Proces, który wspieramy:** cykliczny przegląd listy obserwacyjnej spółek i portfela modelowego
(np. cotygodniowe spotkanie komitetu inwestycyjnego): które spółki analizować głębiej, które są drogie
lub tanie, jakie jest ryzyko portfela i czy zabezpieczać ekspozycję walutową.

### Pytania biznesowe

| # | Pytanie | Decyzja, którą wspiera | Tabela Gold |
|---|---|---|---|
| P1 | Które spółki z listy obserwacyjnej dawały najlepszą stopę zwrotu w relacji do ryzyka, licząc w PLN? | wybór spółek do pogłębionej analizy / zmiany wag | `risk_return` |
| P2 | Czy spółki z USA są dziś wyceniane (P/E) drogo czy tanio względem własnej historii? | moment wejścia / wyjścia, priorytety analiz | `valuation_snapshot`, `fact_valuation_daily` |
| P3 | Jak kurs USD/PLN wpływał na wynik inwestycji w spółki z USA? | czy zabezpieczać ryzyko walutowe (hedging) | `risk_return`, `portfolio_positions_daily` |
| P4 | Kiedy portfel modelowy notował największe spadki i jak zmieniało się jego ryzyko? | limity ryzyka, komunikacja z inwestorami | `portfolio_daily` |

---

## 1. Perspektywa biznesowa

**Kto jest odbiorcą?** Analityk akcji i zarządzający portfelem. Analityk przygotowuje materiały,
zarządzający podejmuje decyzje na komitecie inwestycyjnym.

**Jakie decyzje wspiera rozwiązanie?** Screening spółek (zwrot/ryzyko, wycena P/E na tle historii),
decyzje o zabezpieczeniu walutowym, kontrola ryzyka portfela modelowego (obsunięcia, zmienność).

**Jaka jest wartość i jak ją zmierzyć?**

| Miara (KPI) | Jak mierzymy | Cel |
|---|---|---|
| Czas przygotowania danych na komitet | godziny pracy analityka tygodniowo przed i po wdrożeniu | z kilku godzin do ~0 (dane gotowe rano) |
| Aktualność danych | `fin_ops.pipeline_runs`: godzina zakończenia joba | dane z poprzedniej sesji przed 8:00 |
| Niezawodność | odsetek udanych uruchomień w miesiącu (`pipeline_runs`) | ≥ 95% |
| Wykryte problemy z danymi | liczba testów FAIL/WARN i rekordów w kwarantannie | każdy problem widoczny przed użyciem danych |
| Wykorzystanie | liczba odsłon dashboardu / decyzji komitetu opartych o raport **[do uzupełnienia]** | – |

**Przybliżone koszty utrzymania** (szacunek – **do weryfikacji** z aktualnym cennikiem):

| Pozycja | Projekt (Free Edition) | Wdrożenie produkcyjne |
|---|---|---|
| Platforma Databricks (serverless, job ok. 10 min dziennie) | 0 zł | rząd wielkości kilkudziesięciu USD miesięcznie (zależnie od DBU i regionu) |
| Dane NBP, SEC EDGAR | 0 zł | 0 zł (dane publiczne) |
| Notowania | 0 zł (Stooq, użytek niekomercyjny) | licencja na dane do użytku komercyjnego (dostawca danych / GPW) – zwykle największy koszt |
| Utrzymanie | – | ok. 2–4 h pracy inżyniera danych miesięcznie (aktualizacje, obsługa błędów źródeł) |

## 2. Perspektywa dziedzinowa

Pojęcia i reguły, które musiały znaleźć odzwierciedlenie w danych:

- **Kalendarze sesji:** GPW i giełdy w USA mają różne dni wolne. Budujemy wspólny kalendarz dni sesyjnych;
  w dniu bez sesji na danym rynku przenosimy ostatnią cenę (`is_filled = true`).
- **Kurs średni NBP (tabela A):** publikowany w polskie dni robocze. Do przeliczenia na PLN używamy kursu
  z dnia notowania; gdy NBP nie publikuje (polskie święto), ostatniego opublikowanego (`fx_is_filled`).
  Kurs średni NBP to kurs referencyjny, nie kurs transakcyjny funduszu.
- **Zwrot w PLN vs w walucie notowania:** inwestor rozliczający się w PLN zarabia/traci także na kursie.
  Rozdzielamy efekt ceny i efekt kursowy (`value_pln_fixed_fx`, `fx_effect_pln`, `fx_effect_cagr`).
- **P/E (cena / zysk na akcję):** liczymy z **rocznego rozwodnionego EPS** z raportu 10-K.
  - Używamy tylko raportów **złożonych do SEC do dnia wyceny** (pole `filed`) – w przeszłości analityk nie
    znał jeszcze przyszłych wyników (brak *look-ahead bias*).
  - Rok obrotowy nie musi być kalendarzowy (Microsoft i P&G kończą rok w czerwcu).
  - Przy ujemnym zysku P/E nie ma sensu (NULL); pokazujemy wtedy stopę zysku (earnings yield).
  - Split akcji zmienia EPS historyczny – stąd reguła jakości „podejrzenie splitu” i dobór spółek bez splitów od 2019 r.
- **Spółki z GPW:** nie ma bezpłatnego, legalnego źródła historycznych wyników – P/E liczymy tylko dla USA (ograniczenie).
- **Miary ryzyka:** zmienność roczna = odchylenie standardowe dziennych stóp zwrotu × √252;
  obsunięcie kapitału (drawdown) = spadek od najwyższej dotychczasowej wartości; CAGR = średnioroczna stopa zwrotu;
  zwrot/ryzyko = (CAGR − stopa wolna od ryzyka) / zmienność.
- **Portfel modelowy:** kup i trzymaj, równe wagi 10%, bez kosztów transakcyjnych, dywidend i podatków.

## 3. Perspektywa techniczna

**Architektura:** Databricks (serverless) + Delta Lake + Unity Catalog, warstwy Bronze → Silver → Gold,
orkiestracja jako job (Databricks Asset Bundle). Uzasadnienie i alternatywy: [decyzje.md](decyzje.md).
Diagram: [architektura.md](architektura.md).

**Jak zapewniono jakość?**
- 15 testów na Silver + 7 na Gold, 7 rodzajów reguł; błąd krytyczny zatrzymuje potok przed Gold,
  wyniki w `fin_ops.dq_results` (historia),
- kwarantanna błędnych rekordów z oryginalną treścią i przyczyną,
- testy jednostkowe (pytest) parserów źródeł, transformacji i reguł jakości, uruchamiane automatycznie w GitHub Actions.

**Jak zapewniono powtarzalność?**
- cała logika w kodzie (`src/`), konfiguracja w `config/*.yml`, sekrety poza repozytorium,
- idempotentność: MERGE w Silver (ponowne uruchomienie nie tworzy duplikatów), Gold przebudowywany deterministycznie,
- surowe odpowiedzi źródeł zachowane w Volume – można odtworzyć warstwy bez ponownego pobierania,
- historia zmian tabel Delta (time travel), rejestr uruchomień `fin_ops.pipeline_runs`.

**Co zmienić przy 100× większym wolumenie** (np. 1000 spółek zamiast 10, dane śróddzienne):
- pobieranie: równoległe zapytania z limitem szybkości; SEC – nocny plik zbiorczy `companyfacts.zip` zamiast 1000 zapytań;
  notowania – licencjonowany dostawca z API zbiorczym,
- Bronze: zapis plików do Volume i wczytywanie przez Auto Loader (przyrostowo, ze śledzeniem plików) zamiast `createDataFrame`,
- Silver/Gold: partycjonowanie lub *liquid clustering* po dacie i tickerze; Gold liczony przyrostowo (MERGE ostatnich dni)
  zamiast pełnej przebudowy; okna liczone per ticker (już są partycjonowane),
- jakość: deklaratywne oczekiwania (Lakeflow Declarative Pipelines expectations) i alerty,
- koszty: monitorowanie zużycia DBU, osobne środowiska dev/prod w bundle.

## 4. Perspektywa prawna i etyczna

| Kwestia | Odpowiedź |
|---|---|
| Czy dane można legalnie pozyskać? | **NBP:** dane publiczne, bezpłatne API przeznaczone do automatycznego pobierania. **SEC EDGAR:** dane publiczne rządu USA; przestrzegamy zasad dostępu (User-Agent z kontaktem, ≤ 10 zapytań/s). **Stooq:** pobieranie przez udostępnione API z kluczem, użytek edukacyjny i niekomercyjny; **regulamin Stooq do weryfikacji przez zespół [do uzupełnienia]** – surowych plików nie publikujemy w repozytorium. |
| Dane osobowe? | Nie. Dane dotyczą spółek, kursów i notowań. Jedyna dana kontaktowa (e-mail w User-Agent dla SEC) jest sekretem i nie trafia do repozytorium ani do tabel. |
| Właściciel danych i odpowiedzialność za jakość | Źródłowe: NBP, SEC (sprawozdania – spółki), Stooq. Za przetworzenie i testy jakości odpowiada zespół projektu (właściciel potoku). |
| Ryzyka błędnej interpretacji | wyniki historyczne nie gwarantują przyszłych; P/E z rocznego EPS (nie TTM) może być nieaktualne do 12+ mies.; jednorazowe zdarzenia zaburzają EPS; brak P/E dla GPW; ceny Stooq mogą być korygowane o zdarzenia korporacyjne; **efekt przetrwania** – lista spółek wybrana dziś, a nie w 2019 r.; kurs NBP ≠ kurs transakcyjny. |
| Komunikat dla użytkownika | Dashboard i notatnik analizy zawierają zastrzeżenie: *analiza danych historycznych, nie stanowi rekomendacji inwestycyjnej*. |
