# Słownik danych

Katalog Unity Catalog: `workspace` (konfigurowalny w `config/settings.yml`).
Kolumny techniczne: `_ingest_ts` – czas pobrania (UTC), `_source_file` – ścieżka surowego pliku w Volume,
`_run_id` – identyfikator uruchomienia potoku.

## Bronze (`fin_bronze`) – dane surowe

Wszystkie kolumny biznesowe zapisane jako **tekst, bez zmian** względem źródła. Surowe pliki:
`/Volumes/workspace/fin_bronze/raw/{nbp|stooq|sec}/ingest_date=RRRR-MM-DD/…`.

### `nbp_fx_rates` – źródło: API NBP, tabela A
| Kolumna | Znaczenie | Pole źródła |
|---|---|---|
| currency_code | kod waluty ISO | `code` |
| currency_name | nazwa waluty | `currency` |
| table_type | typ tabeli (A) | `table` |
| table_no | numer tabeli NBP | `rates[].no` |
| effective_date | data publikacji kursu | `rates[].effectiveDate` |
| mid | kurs średni (PLN za 1 jednostkę) | `rates[].mid` |

### `stooq_prices` – źródło: Stooq, CSV dzienny
| Kolumna | Znaczenie |
|---|---|
| ticker | symbol instrumentu w Stooq (z `config/instruments.yml`) |
| date | data sesji |
| open, high, low, close | cena otwarcia, najwyższa, najniższa, zamknięcia (waluta notowania) |
| volume | wolumen (dla indeksów zwykle brak) |

### `sec_eps_facts` – źródło: SEC EDGAR XBRL company facts
| Kolumna | Znaczenie |
|---|---|
| cik | identyfikator spółki w SEC |
| entity_name | nazwa spółki |
| concept, unit | miara (`EarningsPerShareDiluted`) i jednostka (`USD/shares`) |
| period_start, period_end | okres, którego dotyczy wartość |
| val | wartość EPS |
| accn | numer dokumentu (raportu) w EDGAR |
| fy, fp | rok i okres obrotowy **raportu**, w którym podano wartość |
| form | typ raportu: 10-K roczny, 10-Q kwartalny, /A korekta |
| filed | data złożenia raportu w SEC (od kiedy wartość była publicznie znana) |
| frame | okres kalendarzowy przypisany przez SEC (opcjonalnie) |

## Silver (`fin_silver`) – dane oczyszczone

### `fx_rates` – klucz: (currency, date)
| Kolumna | Typ | Znaczenie |
|---|---|---|
| currency | string | kod waluty (wielkie litery) |
| date | date | data kursu |
| rate_mid | double | kurs średni NBP, PLN za 1 jednostkę |
| table_no | string | numer tabeli NBP |

### `prices` – klucz: (ticker, date)
| Kolumna | Typ | Znaczenie |
|---|---|---|
| ticker | string | symbol (małe litery) |
| date | date | data sesji |
| open, high, low, close | double | ceny w walucie notowania |
| volume | double | wolumen |

### `eps_facts` – klucz: (cik, period_start, period_end, accn)
| Kolumna | Typ | Znaczenie |
|---|---|---|
| cik | int | identyfikator SEC |
| entity_name | string | nazwa spółki |
| period_start, period_end | date | okres EPS |
| eps | double | rozwodniony zysk na akcję (USD) |
| accn, form, filed | string, string, date | raport, jego typ i data złożenia |
| fiscal_year, fiscal_period | int, string | rok/okres obrotowy raportu |
| frame | string | okres kalendarzowy SEC |
| duration_days | int | długość okresu w dniach |
| is_annual | boolean | okres roczny (350–380 dni) z raportu 10-K/10-K/A |

### `quarantine` – odrzucone rekordy
| Kolumna | Znaczenie |
|---|---|
| source_table | tabela Bronze, z której pochodzi rekord |
| reject_reason | naruszona reguła (np. `invalid_date`, `non_positive_close`) |
| record_json | oryginalny rekord Bronze (JSON) |
| source_file, ingest_ts | plik źródłowy i czas pobrania |
| quarantined_at | czas odrzucenia |

## Gold (`fin_gold`) – model analityczny

### `dim_instrument` – klucz: ticker (źródło: `config/instruments.yml`, `config/portfolio.yml`)
| Kolumna | Znaczenie |
|---|---|
| ticker, name, market, currency, sector | symbol, nazwa, rynek, waluta notowania, sektor |
| instrument_type | `stock` (spółka) / `index` (indeks odniesienia) |
| sec_cik | CIK w SEC (tylko spółki z USA) |
| in_portfolio, portfolio_weight | czy w portfelu modelowym i z jaką wagą |

### `dim_date` – klucz: date
| Kolumna | Znaczenie |
|---|---|
| date, year, quarter, month, year_month | data i jej części |
| day_of_week | 1 = niedziela … 7 = sobota |
| is_trading_day | czy był notowany co najmniej jeden instrument |

### `fact_fx_daily` – klucz: (currency, date)
| Kolumna | Znaczenie |
|---|---|
| rate_mid | kurs NBP na dzień sesyjny (PLN = 1) |
| fx_is_filled | true = NBP nie publikował, użyto ostatniego kursu |

### `fact_prices_daily` – klucz: (ticker, date); źródło: Silver prices + fx
| Kolumna | Znaczenie |
|---|---|
| close | cena zamknięcia w walucie notowania |
| volume | wolumen (NULL w dni uzupełnione) |
| fx_rate | kurs NBP waluty notowania |
| close_pln | cena w PLN = close × fx_rate |
| daily_return_local, daily_return_pln | dzienna stopa zwrotu w walucie notowania / w PLN |
| is_filled | true = brak sesji na tym rynku, przeniesiona ostatnia cena |
| fx_is_filled | jak w `fact_fx_daily` |

### `fact_valuation_daily` – klucz: (ticker, date); tylko spółki z USA
| Kolumna | Znaczenie |
|---|---|
| close | cena (USD) |
| eps_annual | roczny rozwodniony EPS z ostatniego raportu 10-K znanego w danym dniu |
| eps_period_end, eps_filed, eps_form | okres EPS, data złożenia raportu, typ raportu |
| eps_age_days | ile dni minęło od końca okresu EPS |
| pe_ratio | P/E = close / eps_annual (NULL, gdy EPS ≤ 0) |
| earnings_yield | stopa zysku = eps_annual / close |

### `valuation_snapshot` – klucz: ticker
| Kolumna | Znaczenie |
|---|---|
| as_of_date | ostatni dzień z danymi |
| pe_current, earnings_yield_current | bieżące P/E i stopa zysku |
| pe_median_hist, pe_min_hist, pe_max_hist | mediana, minimum i maksimum P/E z ostatnich `lookback_years` lat |
| pe_percentile_hist | odsetek dni z P/E ≤ bieżącemu (0 = najtaniej, 1 = najdrożej w historii) |
| pe_vs_median | bieżące P/E względem mediany (np. −0,2 = 20% poniżej) |
| hist_days, lookback_years | liczba dni w historii, długość okna (lata) |

### `portfolio_positions_daily` – klucz: (ticker, date)
| Kolumna | Znaczenie |
|---|---|
| weight, units | waga docelowa i liczba jednostek kupionych w dniu startu |
| close, fx_rate, close_pln | cena, kurs, cena w PLN |
| value_pln | wartość pozycji w PLN |
| value_pln_fixed_fx | wartość przy kursie zamrożonym na dzień startu |
| fx_effect_pln | efekt kursowy = value_pln − value_pln_fixed_fx |

### `portfolio_daily` – klucz: date
| Kolumna | Znaczenie |
|---|---|
| value_pln, value_pln_fixed_fx, fx_effect_pln | wartość portfela, przy stałym kursie, efekt kursowy |
| n_positions | liczba pozycji z ceną (kontrola kompletności) |
| daily_return, daily_return_fixed_fx | dzienna stopa zwrotu (z kursem rzeczywistym / stałym) |
| cum_return, cum_return_fixed_fx | skumulowana stopa zwrotu od startu |
| running_max_pln | najwyższa dotychczasowa wartość |
| drawdown | obsunięcie kapitału od szczytu (≤ 0) |
| rolling_volatility | zmienność roczna z ostatnich 30 sesji |

### `risk_return` – klucz: ticker (spółki, indeksy i `PORTFEL`), okres od startu portfela
| Kolumna | Znaczenie |
|---|---|
| start_date, end_date, years, n_days | okres analizy |
| total_return_pln / _local | łączna stopa zwrotu w PLN / w walucie notowania |
| cagr_pln / _local | średnioroczna stopa zwrotu |
| volatility_pln / _local | zmienność roczna (odch. std. dziennych zwrotów × √252) |
| return_to_risk_pln / _local | (CAGR − stopa wolna od ryzyka) / zmienność |
| max_drawdown_pln / _local | największe obsunięcie od szczytu |
| fx_effect_cagr | cagr_pln − cagr_local (efekt kursowy, pkt proc. rocznie) |
| rank_return_to_risk | ranking zwrot/ryzyko w obrębie typu instrumentu |
| name, instrument_type, currency, sector, in_portfolio | atrybuty z `dim_instrument` |

## Operacyjne (`fin_ops`)

### `pipeline_runs`
| Kolumna | Znaczenie |
|---|---|
| run_id, step | uruchomienie i krok potoku |
| status | SUCCESS / FAILED |
| rows_processed | liczba przetworzonych rekordów |
| message | szczegóły lub treść błędu |
| started_at, finished_at | czas rozpoczęcia i zakończenia (UTC) |

### `dq_results`
| Kolumna | Znaczenie |
|---|---|
| run_id | uruchomienie |
| check_name, table_name, rule_type | test, tabela, rodzaj reguły |
| severity | error (zatrzymuje potok) / warn |
| status | PASS / WARN / FAIL |
| failed_count | liczba naruszeń |
| details | przykładowe błędne wartości |
| checked_at | czas wykonania testu |
