# Synchronizacja z upstreamem

**Rekomendacja: scal (`git merge upstream/main` do `main`), nie rebase ani
cherry-pick.** Fork ma 13 publicznych commitów od rozwidlenia; rebase przepisałby
tę historię (force-push na publiczny fork) i kazał odtwarzać te same konflikty
13 razy. Cherry-pick jest do wybiórczego brania — a chcemy wszystkie 18 commitów
upstreamu. Merge rozwiązuje konflikty raz, jednym commitem scalającym, i zachowuje
obie historie.

## Stan w liczbach

- Baza rozwidlenia: `a393061` (2026-09-11, „UI mobilne: zakładka Aktywności… (25.1.0)").
- Upstream od bazy: **18 commitów** (`a393061..upstream/main`), najnowszy **2026-10-06**, `VERSION` upstreamu **26.2.5**.
- Fork od bazy: **13 commitów**, `VERSION` forka **25.5.0**.
- Konflikty tekstowe (`git merge-tree --write-tree upstream/main main`): **4 pliki,
  9 hunków** + **1 konflikt semantyczny** w testach, którego merge-tree nie widzi.
  `app/db.py`, `app/models.py`, `app/config.py`, `app/templates/privacy.html`,
  `deploy/*` scalają się automatycznie.

```text
          25.1.0 (baza a393061, 2026-09-11)
          │
  ┌───────┴────────┐
  │ main (fork)     │ upstream/main
  │ 13 commitów     │ 18 commitów  → 26.2.5 (2026-10-06)
  │ → 25.5.0        │
  │ OIDC, Vertex,   │ prognoza dnia, dedup aktywności,
  │ utwardzenie,    │ kolejka/timeouty LLM, UX zdjęcia
  │ Android, Terraform
  └───────┬────────┘
          ▼  git merge upstream/main  (1 commit scalający, 4 pliki w konflikcie)
```

## Zmiany upstreamu (pogrupowane, z wpływem na użytkownika)

- **Prognoza dnia i kalibracja** (`services/day.py`, `energy.py`,
  `calibration.py`, `models.py`, `db.py`; 26.0.0–26.1.0, 25.2.1): bilans od rana
  zakłada zwykły trening użytkownika, policzony **konserwatywnie na 75%**
  (`forecast_hour_local` zapisuje godzinę prognozy). Kalibracja pomija dni
  częściowo zalogowane i nie wywala się dla kont bez dziennego totalu z Garmina.
- **Deduplikacja aktywności** (`services/activity_dedup.py` — nowy, `strava.py`,
  `meals.py`; 25.2.2–25.2.3): trening zsynchronizowany i dopisany ręcznie liczony
  **raz**; zawyżone czasy nie zerują już treningu ze Stravy.
- **Kolejka i szacowanie posiłków** (`services/meal_queue.py`, `meal_vision.py`,
  `routers/meals.py`, `config.py`; 25.1.1, 25.2.0, 26.2.1–26.2.2): kolejka zdjęć
  robi backoff retry i kaskadę modeli Gemini, pokazuje realny powód błędu
  i ostrzeżenie o kluczu, szacowanie zeszło z pętli zdarzeń, dodane timeouty na
  wywołania LLM. `estimate_from_photo`/`estimate_from_text` zwracają teraz
  **krotkę `(oszacowanie, model)`** zamiast samego oszacowania. **Tu nachodzi na
  backend Vertex z forka.**
- **UX zdjęcia w mobile** (`templates/mobile.html`, `static/sw.js`,
  `usage.html`; 26.1.1–26.2.5): postęp i etap błędu przy szacowaniu, szacunek pod
  kartą wagi w tabie „Dodaj", ekran nie gaśnie w trakcie, service worker
  przepuszcza żądania nie-GET.
- **Statystyki** (`services/usage.py`, `usage.html`): nowe liczniki prognozy
  i kolejki na `/usage`.
- **Deploy** (`deploy/fit-krasnal*.service`, `deploy/README.md`; 26.2.3): szybsze
  zamknięcie uvicorna przy deployu, log dostępu Caddy.
- **Migracje w `app/db.py`**: +`forecast_hour_local` (daily_summary),
  +`next_attempt_at`, +`last_error_kind` (pending_meal).
- **Prywatność**: upstream **nie ruszył** `privacy.html` ani `PRIVACY_VERSION`
  (u niego nadal 2026-09-11).
- **Testy**: 6 nowych plików: `test_activity_dedup`, `test_calibration_non_garmin`,
  `test_calibration_partial_days`, `test_forecast_hour`, `test_forecast_workout`,
  `test_resting_cap`.

## Konflikty i rozwiązanie każdego

Hunki policzone z `git merge-tree --write-tree upstream/main main`.

| Plik | Hunki | Natura | Rozwiązanie |
|---|---|---|---|
| `VERSION` | 1 | fork 25.5.0 vs upstream 26.2.5 | **Ręczny łączony bump** — patrz niżej. |
| `app/services/meal_vision.py` | 4 | obie strony przebudowały backend Gemini: fork dodał ścieżkę Vertex (`gemini_client`, ADC, bez klucza), upstream dodał timeouty, kaskadę modeli, `classify_error` i krotkę w zwrocie | **Integracja ręczna, oba.** Najdroższy punkt: zachowaj kaskadę/timeouty/klasyfikację błędu upstreamu **i** klienta Vertex z forka; ścieżka Vertex też musi zwracać `(oszacowanie, model)`. |
| `app/services/usage.py` | 1 | ten sam zbiór `EVENTS`: fork dopisał `login_google` + zdarzenia mostka Android, upstream swoje | **Suma obu** — wklej zdarzenia z obu stron do jednego zbioru. Trywialne. |
| `app/templates/mobile.html` | 3 | fork dodał most natywny Capacitora, upstream przebudował UX szacowania zdjęcia | **Oba.** Bloki są w większości rozłączne; rozwiąż blok po bloku, zachowując most natywny **i** nowy feedback szacowania. |
| `tests/test_meal_vision.py` | semantyczny | fork dodał ten plik (upstream go nie dotyka → scala się „czysto"), ale linia `assert out is est` zakłada pojedynczy zwrot, a upstream zwraca krotkę | **Popraw test**: rozpakuj `est, model = meal_vision.estimate_from_text(...)`. Bez tego suita jest czerwona po scaleniu. |

- `app/db.py`, `app/models.py` — **bez konfliktu**, ale obie strony dodają
  migracje (fork: `google_sub` na `user`; upstream: trzy kolumny wyżej). Addytywne,
  strażone `PRAGMA table_info`, na różnych tabelach → współżyją, kolejność bez
  znaczenia. Po scaleniu zweryfikuj, że obie przechodzą na istniejącej bazie VM.
- `app/config.py` — bez konfliktu; wygrywa `PRIVACY_VERSION` forka (2026-09-16),
  bo upstream swojej linii nie zmieniał.
- `DONE.md` — scala się automatycznie, ale wpis o samym scaleniu dopisz **ręcznie**
  (jak każdy „done"), razem z łączonym bumpem `VERSION`.

### Łączony bump `VERSION` (wg VERSIONING.md)

Baza upstreamu to 26.2.5; fork wnosi nierozliczone funkcje (OIDC 25.3, Vertex
25.4, utwardzenie 25.5) **i zmianę noty prywatności**, która wg VERSIONING.md
bumpuje X. Ustaw **`27.0.0`**. Nie bierz „czyjejś" wartości — to jedna decyzja
człowieka w commicie scalającym.

## Koszt i ryzyka

**Szacunek: ~4 h dla człowieka.** `usage.py`, `VERSION` i poprawka testu po ~5 min,
`db`/`models` auto (tylko weryfikacja), `mobile.html` ~1 h (3 bloki),
`meal_vision.py` ~1,5–2 h (trzeba zrozumieć i Vertex, i kaskadę/timeouty),
reszta na testy i wpisy `DONE.md`/`VERSION`.

Ryzyka:
- **Kolejność migracji**: niskie. Idempotentne i addytywne, ale puść `_migrate`
  na kopii bazy VM, zanim pójdzie na produkcję.
- **`PRIVACY_VERSION`**: fork podbił ją do 2026-09-16 (commit 0b01a60, razem
  z tekstem o Vertex AI i logowaniu Google w `privacy.html`); upstream został na
  2026-09-11; po scaleniu obowiązuje 2026-09-16. Scalenie nie dodaje nowego
  odbiorcy danych → bez kolejnego bumpu. Sprawdź tylko, czy testerzy forka
  zaakceptowali już wersję 2026-09-16.
- **`mobile.html`**: zgubiony blok = zepsuty SPA. Po scaleniu otwórz `/mobile`
  i sprawdź, że działa i most Android, i nowy feedback szacowania zdjęcia.

## Statystyki (co sprawdzić na `/usage` po wdrożeniu)

- liczniki upstreamu: prognoza dnia (trafność vs. `kcal_total_garmin`) i kolejka
  zdjęć (retry, `last_error_kind`) — potwierdzają, że logika upstreamu działa;
- liczniki forka: `login_google`, `native_app_open`, `photo_native_*`,
  `steps_health_connect` — potwierdzają, że scalenie nie zgubiło zdarzeń forka
  (suma zbiorów `EVENTS`).

## Sekwencja komend

Warunek wejścia: `git status` **czyste** — zwłaszcza bez zmian w `deploy/`
(upstream zmienia `deploy/README.md` i `deploy/fit-krasnal*.service`; brudne
drzewo = `git merge` przerwie się na starcie). Niezakończone prace w `deploy/`,
`android-app/` i `VERSION` najpierw commitnij.

```sh
git fetch upstream
git checkout main
git merge --no-ff upstream/main          # konflikty: VERSION, meal_vision.py, usage.py, mobile.html
# rozwiąż: usage.py (suma), VERSION (27.0.0), mobile.html (oba), meal_vision.py (oba)
# popraw tests/test_meal_vision.py (krotka w zwrocie), dopisz łączony wpis do DONE.md
git add VERSION app/services/meal_vision.py app/services/usage.py app/templates/mobile.html \
        tests/test_meal_vision.py DONE.md
.venv/bin/pytest tests/test_meal_vision.py tests/test_queue_settings.py tests/test_usage.py   # testy zmienianych plików
.venv/bin/pytest                         # pełna suita — za zgodą właściciela
# czerwone → napraw przed commitem; czerwonego scalenia nie commituj
git commit                               # commit scalający
```

**Deploy — uwaga:** fork **nie** wdraża przez GitHub Actions. Workflow
`.github/workflows/deploy.yml` odziedziczony z upstreamu wdraża produkcję autora
i na forku ma być wyłączony (punkt „GitHub Actions wyłączone na forku" w
[publikacja-i-przekazanie.md](publikacja-i-przekazanie.md)). Wdrożenie forka:
push na `origin/main` robi właściciel, potem ręcznie `gcloud compute ssh …
--tunnel-through-iap` i `bash /opt/fit-krasnal/deploy/deploy.sh` (pobiera
`origin/main` i restartuje usługę). Sekwencja tego planu kończy się na commicie.
