# Financial Data Lakehouse – scenariusz prezentacji i plan zaliczenia

**Materiały:** prezentacja `Financial_Data_Lakehouse_Prezentacja_Zaliczenie.pptx` (15 slajdów, z notatkami prowadzącej) oraz wersja PDF. Pliki prezentacji zostały przygotowane do pobrania w rozmowie; ten dokument archiwizuje scenariusz i instrukcje demonstracji w repozytorium.

**Zalecany czas:** około 9–12 minut omówienia + 2 minuty demonstracji. Gdy czas jest krótszy, szybko przejdź przez slajdy 5–6 i 14; dokładniej pokaż architekturę (4), testy (7), automatyzację (8) i dashboard (13–15).

**Ważne:** liczby i wykresy pokazują stan danych z 04.11.2026. Gdy dane zaktualizują się ponownie, dashboard będzie pokazywał inne wartości niż historyczny zrzut w prezentacji; to oczekiwane zachowanie.

## Tekst do powiedzenia przy slajdach

### 01. Wprowadzenie: Financial Data Lakehouse

Na początku powiedz krótko: „Zrobiłam projekt, który zbiera trzy rodzaje danych finansowych, porządkuje je w Databricks i codziennie przygotowuje analizę portfela. Pokażę architekturę, testy jakości, wyniki i działający dashboard”. Nie rozwijaj tutaj szczegółów technicznych.

### 02. Problem biznesowy i cztery pytania

Problem jest typowy dla analizy finansowej: kursy walut, dane giełdowe i wyniki spółek mają różne formaty i kalendarze. Gdy robi się to ręcznie w Excelu, łatwo o niespójności. W tym projekcie interesowały mnie cztery konkretne pytania: rentowność, wycena, ryzyko walutowe i obsunięcie portfela.

### 03. Zakres portfela i źródła danych

Świadomie ograniczyłam zakres do pięciu amerykańskich spółek: Apple, Microsoft, Coca-Cola, JPMorgan i Exxon Mobil. Każda dostała 20% początkowego kapitału 100 tys. zł. Dane pochodzą z NBP, FMP i SEC. NBP pobieramy dla USD i EUR, choć sam portfel ma spółki w USD. Wyniki analizujemy od początku 2023 roku do 4 listopada 2026.

### 04. Architektura Bronze–Silver–Gold

To jest główny diagram architektury. Bronze zachowuje surowe odpowiedzi źródeł i metadane pobrania. Silver nadaje typy, usuwa duplikaty i odkłada niepoprawne rekordy do kwarantanny. Gold buduje końcowy model analityczny. Osobny schemat fin_ops zapisuje przebieg uruchomień i wyniki testów. Wszystko działa w Databricks, na tabelach Delta Lake.

### 05. Transformacje i reguły dziedzinowe

Oprócz podziału na warstwy istotne są reguły dziedzinowe. Dane z NBP i giełdy mają inne kalendarze, dlatego tworzymy wspólną oś sesji i w razie potrzeby używamy ostatniego znanego kursu. P/E nie może wykorzystywać przyszłych raportów, dlatego w modelu jest warunek z datą filed. Dla Silver zastosowałam MERGE, żeby powtórne uruchomienie nie dublowało rekordów.

### 06. Model danych: dziewięć tabel Gold

Warstwa Gold ma dziewięć tabel. Pierwsze dwie to wymiary instrumentu i daty. Kolejne cztery służą do dziennych cen, kursów i wycen P/E. Ostatnie trzy opisują pozycje portfela, jego wartość oraz ranking zwrotu i ryzyka. Dzięki temu dashboard czyta gotowe dane zamiast ponownie przeliczać wszystko na wykresach.

### 07. Kontrola jakości danych

W ostatnim uruchomieniu mamy 22 testy, z czego 21 zakończyło się PASS, jeden dał WARN i żaden nie dał FAIL. Ostrzeżenie dotyczy historycznych danych EPS, w których pojawiają się różnice typowe dla korekt po splitach. Osobnym SQL-em sprawdziłam, że wskaźniki liczone w latach 2023–2026 nie wykorzystują tych najstarszych podejrzanych okresów. Nie wyłączamy ostrzeżenia, bo pokazuje, że kontrola faktycznie działa.

### 08. Automatyzacja i monitoring

Automatyzacja składa się z siedmiu zadań. Po setup trzy pobrania mogą działać równolegle, potem Silver, kontrola jakości i Gold. Test przyrostowy zakończył się sukcesem w 3 minuty 43 sekundy. Ustawiłam harmonogram od poniedziałku do piątku o 7:30 oraz alert e-mail w razie niepowodzenia. Dashboard ma osobne odświeżenie o 8:00. Trzeba zaznaczyć, że pierwszego cyklicznego uruchomienia nie zweryfikowaliśmy jeszcze na etapie przygotowania prezentacji.

### 09. Najważniejsze KPI

To kluczowe liczby z końcowego dashboardu: kapitał początkowy wynosi 100 tys. zł, a wartość końcowa około 191 tys. zł. Skumulowana stopa zwrotu to 91,16%, CAGR 18,4%. Największe obsunięcie od wcześniejszego maksimum wyniosło minus 19,36%. To wynik portfela modelowego, bez kosztów, podatków, rebalancingu i w standardowej wersji bez osobnego doliczania dywidend.

### 10. P1 i P2: zwroty oraz wycena

Pierwsze pytanie dotyczyło tego, która ze spółek najwięcej zarobiła w PLN. W obecnym zestawie na prowadzeniu jest Apple; w samym notebooku P1 dodatkowo liczymy zmienność i relację zwrotu do ryzyka. Drugie pytanie dotyczyło wyceny P/E. Tu porównuję bieżący wskaźnik z jego medianą historyczną. Ważne: nie nazywam spółki automatycznie tanią lub drogą w sensie inwestycyjnym, tylko pokazuję pozycję względem jej własnej historii.

### 11. P3: wpływ USD/PLN

To jedna z ciekawszych części. Spółki są amerykańskie, ale polski inwestor patrzy na wynik w złotych. W danych widać, że CAGR w USD jest większy niż w PLN dla każdej spółki. Na drugim wykresie porównuję rzeczywistą wartość portfela z hipotetyczną, przy utrzymaniu kursu walutowego z dnia startu. Różnica pokazuje skalę oddziaływania walut, ale scenariusz nie jest tożsamy z rzeczywistym hedgingiem.

### 12. P4: ryzyko i drawdown

To wykres ryzyka portfela. Największy spadek od poprzedniego maksimum pojawił się wiosną 2025 roku i wyniósł około 19,36%. Ważne, że nie sumujemy obsunięć z kolejnych dni. Na wykresie mamy minimum dziennej wartości drawdown w miesiącu. Dzięki temu skala spadku jest poprawna. Wniosek dla analityka: sama stopa zwrotu nie pokazuje, jakie wahania trzeba było zaakceptować po drodze.

### 13. Dashboard AI/BI

Tu pokazuję gotowy produkt. Dashboard jest opublikowany w Databricks. Widoczne są cztery miary portfela, pięć wykresów i dwa filtry. Testowałam wybór spółki i dat, np. ograniczenie serii do 2025 roku. Definicja dashboardu jest wyeksportowana do JSON i zapisana w GitHubie, więc nie jest to coś istniejącego tylko w moim koncie Databricks.

### 14. Ograniczenia i dalszy rozwój

Przy prezentacji warto też powiedzieć, czego ten projekt nie robi. Nie jest systemem produkcyjnym dla prawdziwego funduszu. Mamy tylko pięć spółek USA i uproszczony portfel, a P/E nie jest liczone z ostatnich czterech kwartałów. Wersja darmowa Databricks ma limity. Następne kroki to m.in. porównanie z indeksem S&P 500, rozbudowa wycen o TTM i test odtworzenia projektu w czystym workspace.

### 15. Demonstracja na żywo

Na koniec przechodzę do krótkiej demonstracji. Pokazuję udany job w Jobs & Pipelines, tabele Gold w Catalog Explorer, wynik testów w SQL Editor, a potem dashboard. W filtrze spółki wybieram Apple, potem wracam na All i ograniczam zakres dat do 2025 roku. Na koniec otwieram GitHub, gdzie jest definicja joba, notebooki i eksport dashboardu. Taki pokaz trwa około dwóch minut.

## Demonstracja na żywo – plan w 120 sekund

1. **Jobs & Pipelines → `[dev ...] fin-lakehouse-pipeline`**: pokaż `Succeeded` oraz zadania `setup`, `ingest_nbp`, `ingest_fmp`, `ingest_sec`, `silver`, `quality_silver`, `gold`. Podkreśl, że trzy pobrania mogą działać równolegle.
2. **Catalog Explorer → `workspace.fin_gold`**: pokaż tabele `fact_prices_daily`, `portfolio_daily`, `valuation_snapshot`, `risk_return`. W razie potrzeby pokaż wcześniej uruchomione SQL z licznikami rekordów.
3. **SQL Editor:** pokaż wynik 22 testów z `workspace.fin_ops.dq_results` dla ostatniego uruchomienia:

   ```sql
   WITH ostatni_run AS (
       SELECT run_id
       FROM workspace.fin_ops.dq_results
       GROUP BY run_id
       ORDER BY MAX(checked_at) DESC
       LIMIT 1
   )
   SELECT d.status, d.severity, COUNT(*) AS liczba_testow,
          SUM(d.failed_count) AS naruszenia
   FROM workspace.fin_ops.dq_results d
   JOIN ostatni_run r ON r.run_id = d.run_id
   GROUP BY d.status, d.severity
   ORDER BY d.status, d.severity;
   ```

   Ostatni potwierdzony wynik (04.11.2026): 15 `PASS/error`, 6 `PASS/warn`, 1 `WARN/warn`, 0 `FAIL`.
4. **Dashboard → Financial Data Lakehouse:** ustaw `Wybierz spółkę` na Apple, następnie `All`. Ustaw daty od `01.01.2025` do `31.12.2025`, pokaż reakcję wykresów czasowych i wyczyść filtr.
5. **GitHub:** otwórz repozytorium i wskaż `databricks.yml`, `notebooks/`, `src/`, `tests/` oraz `dashboards/financial-data-lakehouse.lvdash.json`.

## Pytania, które może zadać prowadzący

**1. Po co trzy warstwy Bronze, Silver, Gold?**  
Bronze zachowuje dane źródłowe do odtworzenia, Silver nadaje jednolity schemat i usuwa błędy, a Gold buduje model do raportowania. Oddzielenie etapów ułatwia debugowanie i kontrolę pochodzenia danych.

**2. Co się stanie po ponownym uruchomieniu joba?**  
Bronze pobiera dane przyrostowo, w FMP ponawia ostatnie 7 dni dla korekt. Silver używa `MERGE` po kluczach biznesowych, a Gold przebudowuje wyniki deterministycznie, więc duplikaty z pobrania nie powinny mnożyć obserwacji w analizie.

**3. Jak ograniczasz błąd typu look-ahead bias przy P/E?**  
Dla historycznej daty wyceny biorę tylko te raporty SEC, których data `filed` nie przekracza daty wyceny. Wykorzystuję roczny rozwodniony EPS, nie TTM.

**4. Dlaczego jeden test jakości ma status WARN?**  
Historyczne roczne wartości EPS dla tego samego okresu różnią się istotnie między zgłoszeniami SEC. To może wynikać z korekt po splitach; nie wyłączam kontroli. Dodatkowe zapytanie wykazało, że wyceny w latach 2023–2026 nie korzystają z podejrzanych EPS kończących się w latach 2010–2018.

**5. Czy wyniki uwzględniają dywidendy, podatki i koszty?**  
Nie są to wyniki rzeczywistego funduszu. To uproszczony model buy & hold, z początkowymi wagami 20%, bez rebalancingu, opłat transakcyjnych i podatków. Dywidendy nie są osobno doliczane (mogą częściowo wpływać na ceny skorygowane zależnie od źródła).

**6. Dlaczego CAGR w PLN jest niższy niż w USD?**  
Inwestor z Polski odczuwa zarówno zmianę ceny akcji w USD, jak i zmianę kursu USD/PLN. W badanym okresie efekt walutowy działał niekorzystnie na przeliczoną stopę zwrotu.

**7. Co świadczy o tym, że automatyzacja naprawdę działa?**  
Pierwsze testowe wykonanie całego joba w trybie incremental zakończyło się statusem `Succeeded` w 3 min 43 s. W Gold widać nowe dane. Harmonogram na 07:30 i alert On failure zostały wdrożone; pierwszą rzeczywistą realizację harmonogramu trzeba zweryfikować po jej wystąpieniu.

**8. Jakie są ograniczenia produkcyjne?**  
Databricks Free Edition ma limity, FMP wymaga określonej licencji przy użyciu komercyjnym, a brak danych śróddziennych i prosty model portfela ograniczają zakres zastosowań. Do produkcji potrzebne byłyby monitoring, test odtwarzania i licencjonowane źródła.

## Kontrola przed prezentacją

- [ ] Otwórz PPTX i upewnij się, że czcionki oraz polskie znaki wyświetlają się poprawnie.
- [ ] Przygotuj lokalnie również PDF — wygodny zapasowy format.
- [ ] W Databricks zaloguj się wcześniej, aby nie tracić czasu na weryfikację konta.
- [ ] Sprawdź, czy opublikowany dashboard się otwiera i czy obydwa filtry reagują.
- [ ] Sprawdź ostatni status joba i nie przedstawiaj testowego `Succeeded` jako dowodu pierwszego planowego uruchomienia.
- [ ] Sprawdź liczniki Gold i wyniki jakości po najnowszym uruchomieniu; mogą się zmienić po 04.11.2026.
- [ ] Miej otwarte karty: Job → Catalog → SQL Editor → Dashboard → GitHub.
- [ ] Nie pokazuj klucza API FMP, sekretu SEC ani konfiguracji zawierającej ich wartości.
- [ ] Obejrzyj dashboard na projektorze w 100% i sprawdź, czy treści wykresów są czytelne.
- [ ] Zrób krótką próbę z zegarkiem i zachowaj 2 minuty na demonstrację.

## Materiały w repozytorium

- [Projekt i kod](https://github.com/bajerynastudia-beep/financial-data-lakehouse)
- [Architektura](https://github.com/bajerynastudia-beep/financial-data-lakehouse/blob/main/docs/architektura.md)
- [Automatyzacja](https://github.com/bajerynastudia-beep/financial-data-lakehouse/blob/main/docs/automatyzacja.md)
- [Dashboard JSON](https://github.com/bajerynastudia-beep/financial-data-lakehouse/blob/main/dashboards/financial-data-lakehouse.lvdash.json)

**Uwaga o wersjonowaniu:** jeśli prezentacja ma być odtwarzana w przyszłości, podaj datę stanu danych. Aktualne wyniki dashboardu będą się zmieniać po kolejnych cyklach ładowania.