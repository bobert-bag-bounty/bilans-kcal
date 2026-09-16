import type { CapacitorConfig } from '@capacitor/cli';

// URL zdalnej aplikacji. Produkcja domyślnie; do testów w LAN:
//   FIT_KRASNAL_APP_URL=http://192.168.1.10:8000 npx cap sync android
const appUrl = process.env.FIT_KRASNAL_APP_URL || 'https://fit.krasnal.cc';
const appHost = new URL(appUrl).host;
const isHttp = appUrl.startsWith('http://');

const config: CapacitorConfig = {
  appId: 'cc.krasnal.fit',
  appName: 'Fit Krasnal',
  webDir: 'www',
  server: {
    url: appUrl,
    allowNavigation: [appHost],
    androidScheme: 'https',
    cleartext: isHttp,
  },
  android: {
    allowMixedContent: isHttp,
  },
  plugins: {
    StatusBar: {
      overlaysWebView: false,
      style: 'LIGHT',
      backgroundColor: '#ffffff',
    },
  },
};

export default config;
