// Minimal service worker — enables PWA "Add to Home Screen".
// App requires network access; no offline caching intentional.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", () => self.clients.claim());
// Only GET goes through the worker: proxying a large POST (meal photo) via
// respondWith(fetch(request)) can drop the body on mobile ("network error").
// Without respondWith the browser handles non-GET requests natively.
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request));
});
