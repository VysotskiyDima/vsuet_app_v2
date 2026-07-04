const CACHE_NAME = "vsuet-rating-v23";
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./styles.css?v=15",
  "./resources/logo.svg",
  "./resources/logo-192.png",
  "./resources/logo-512.png"
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
  if (e.request.method !== "GET") return;

  // Helper function to fetch with a timeout of 2.5 seconds (to prevent hanging in semi-offline local network)
  const fetchWithTimeout = (request, timeout = 2500) => {
    return new Promise((resolve, reject) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
        reject(new Error("Timeout"));
      }, timeout);

      fetch(request, { signal: controller.signal })
        .then((response) => {
          clearTimeout(timeoutId);
          resolve(response);
        })
        .catch((err) => {
          clearTimeout(timeoutId);
          reject(err);
        });
    });
  };

  // Network-First для всего: всегда идём в сеть, кэш — только офлайн-фолбэк
  e.respondWith(
    fetchWithTimeout(e.request)
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
        return caches.match(e.request, { ignoreVary: true }).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse;
          // Открытие страницы офлайн без кэша конкретного URL — отдаём оболочку приложения
          if (e.request.mode === "navigate") {
            return caches.match("./index.html", { ignoreVary: true });
          }
          // Return 504 to prevent browser from falling back to network and hanging
          return new Response(JSON.stringify({ error: "Offline and no cache" }), {
            status: 504,
            statusText: "Gateway Timeout",
            headers: { "Content-Type": "application/json" }
          });
        });
      })
  );
});
