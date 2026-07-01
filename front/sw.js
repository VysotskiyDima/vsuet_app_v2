const CACHE_NAME = "vsuet-rating-v1";
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./styles.css",
  "./logo.svg",
  "./logo-192.png",
  "./logo-512.png"
];

// Install Event: cache static assets
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Event: clean up old caches
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event: handle network requests with PWA strategies
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // For API requests, use Network-First strategy (with cache fallback so user can view data offline)
  if (url.pathname.includes("/students/") || url.pathname.includes("/rating/")) {
    e.respondWith(
      fetch(e.request)
        .then((response) => {
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(e.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(e.request);
        })
    );
  } else {
    // For static files (HTML, CSS, JS, fonts), use Stale-While-Revalidate
    e.respondWith(
      caches.match(e.request).then((cachedResponse) => {
        if (cachedResponse) {
          // Fetch updated version in background to update cache
          fetch(e.request)
            .then((response) => {
              if (response.status === 200) {
                caches.open(CACHE_NAME).then((cache) => {
                  cache.put(e.request, response);
                });
              }
            })
            .catch(() => {/* Ignore errors offline */});
          return cachedResponse;
        }
        return fetch(e.request);
      })
    );
  }
});
