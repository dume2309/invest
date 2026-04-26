// Service Worker — Portfolio Tracker
// Stratégie : network-first pour HTML/JSON, cache-first pour assets statiques
const CACHE = "invest-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
  "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Ne JAMAIS cacher les appels API (cours, GitHub)
  if (url.host.includes("yahoo.com") || url.host.includes("corsproxy") ||
      url.host.includes("allorigins") || url.host.includes("api.github.com") ||
      url.host.includes("stooq") || url.host.includes("frankfurter")) {
    return;
  }
  // Network-first sur HTML, cache fallback
  if (e.request.mode === "navigate" || e.request.destination === "document") {
    e.respondWith(
      fetch(e.request)
        .then((r) => { caches.open(CACHE).then((c) => c.put(e.request, r.clone())); return r; })
        .catch(() => caches.match(e.request).then((r) => r || caches.match("./index.html")))
    );
    return;
  }
  // Cache-first pour assets
  e.respondWith(
    caches.match(e.request).then((r) => r || fetch(e.request).then((resp) => {
      caches.open(CACHE).then((c) => c.put(e.request, resp.clone()));
      return resp;
    }))
  );
});
