// Service worker for offline support. Deliberately small: it caches the app
// shell so the site opens without a network, and keeps the most recent copy of
// the product catalog so the ordering screen has something to show offline.
//
// Strategy per request type:
//  - navigations (HTML pages): network-first, fall back to the cached shell
//  - the products API GET: network-first, fall back to the last cached list
//  - everything else: left alone (let the browser handle it normally)
//
// We never cache authenticated calls other than the catalog, and never cache
// non-GET requests — stale orders or a cached login would be worse than an
// honest network error.

const CACHE = "farm-cache-v1";

self.addEventListener("install", (event) => {
  // Activate this worker immediately rather than waiting for old tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Drop caches from older versions.
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isProducts = url.pathname === "/products" || url.pathname.endsWith("/products");

  // Cache the catalog: try the network, save a fresh copy, fall back to cache.
  if (isProducts) {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
          return res;
        })
        .catch(() => caches.match(request)),
    );
    return;
  }

  // Page navigations: network-first, cached shell as a fallback.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
          return res;
        })
        .catch(() => caches.match(request)),
    );
  }
});
