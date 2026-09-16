# Fit Krasnal — powłoka Android (Capacitor, PoC)

Natywna „skorupa" dla https://fit.krasnal.cc. WebView ładuje **zdalną** stronę
produkcyjną; cały interfejs to `app/templates/mobile.html` z backendu. Strona
wykrywa `window.Capacitor` i woła wtyczki natywne.

## Wymagania

- Node 24, npm.
- JDK **21** (`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`; JDK 25 psuje Gradle).
- Android SDK z `platforms;android-36` i `build-tools;35.0.0`
  (`ANDROID_HOME` wskazuje katalog SDK; brakujące pakiety doinstaluje
  `sdkmanager`).

## Build

```bash
cd android-app
npm install
export ANDROID_HOME=/sciezka/do/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
npx cap sync android          # przepisuje capacitor.config.ts → android/
cd android && ./gradlew assembleDebug
# wynik: android/app/build/outputs/apk/debug/app-debug.apk
```

Skróty: `npm run sync`, `npm run build`.

## Zmienne środowiskowe

| Zmienna | Znaczenie |
|---|---|
| `FIT_KRASNAL_APP_URL` | URL ładowany w WebView. Domyślnie `https://fit.krasnal.cc`. Dla testów w LAN: `FIT_KRASNAL_APP_URL=http://192.168.1.10:8000 npx cap sync android` — wtedy config włącza `cleartext` i mixed content. |

Zmiana URL wymaga ponownego `npx cap sync android` i przebudowy APK.

## Instalacja na telefonie

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n cc.krasnal.fit/.MainActivity
```

Minimalny Android: **8.0 (API 26)** — wymaga tego biblioteka Health Connect.

## Co udostępnia powłoka (wtyczki)

| Wtyczka | Do czego |
|---|---|
| `@capacitor/camera` | zdjęcie posiłku z aparatu / galerii (uprawnienie `CAMERA` w manifeście) |
| `@capacitor/haptics` | wibracja przy zapisie |
| `@capacitor/app` | zdarzenia tła/pierwszego planu, przycisk Wstecz |
| `@capacitor/status-bar` | kolor paska statusu |
| `capacitor-health` | Health Connect: odczyt **kroków** i **wagi** (`READ_STEPS`, `READ_WEIGHT`) + ekran uzasadnienia uprawnień |

Identyfikator aplikacji: `cc.krasnal.fit`. Ikona launchera pochodzi
z `app/static/icon-512.png`.

## Most Capacitora a nawigacja po POST

Powłoka wstrzykuje `window.Capacitor` tylko przy ładowaniu dokumentu przez GET.
Po wysłaniu formularza (logowanie, rejestracja, wylogowanie → 303 → GET) strona
ładuje się bez mostka. Dlatego powłoka dokleja do User-Agent `FitKrasnalApp/1`,
a `mobile.html`, `login.html` i `register.html` przeładowują się jednorazowo,
gdy widzą ten marker bez `window.Capacitor` (od wersji 25.2.2 backendu).

## Test na urządzeniu (bez logowania w GUI)

W buildzie debug WebView jest debugowalny. Po `adb reverse tcp:8000 tcp:8000`
i buildzie z `FIT_KRASNAL_APP_URL=http://localhost:8000` można sterować stroną
przez Chrome DevTools Protocol (`adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>`).
Sprawdzone w ten sposób: wstrzyknięcie mostka, przyciski aparatu/galerii,
`HealthPlugin.isHealthAvailable()` → `true` przy zainstalowanym Health Connect,
start intencji aparatu i dialogu uprawnień Health Connect.

## Tylko PoC — czego tu nie ma

- Brak podpisu release (tylko `assembleDebug`); brak Play Store.
- Brak trybu offline: bez sieci WebView pokazuje błąd. `www/index.html` to
  placeholder, nie działa jako fallback.
- Health Connect na Androidzie 11 wymaga osobnej aplikacji Health Connect
  ze sklepu Play; na 14+ jest w systemie. Zapis danych do Health Connect
  nie jest włączony.
- Wtyczka `capacitor-health-connect` została odrzucona (wspiera tylko
  Capacitor 5); zastąpiona przez `capacitor-health`.
- Strona po stronie backendu musi sama sprawdzać `window.Capacitor`
  i wołać wtyczki — powłoka nic nie wstrzykuje poza standardowym mostkiem.
