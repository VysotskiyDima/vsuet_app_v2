const CACHE_NAME = "vsuet-rating-v29";
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./styles.css?v=20",
  "./resources/logo.svg",
  "./resources/logo-192.png",
  "./resources/logo-512.png"
];

// Расширения, которые считаем "статикой" для Cache-First,
// даже если их не было в STATIC_ASSETS на момент install
// (например, шрифты, подгружаемые динамически через CSS).
const STATIC_EXTENSIONS = /\.(?:js|css|woff2?|ttf|svg|png|jpg|jpeg|gif|ico)(?:\?.*)?$/;

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

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

const fetchWithTimeout = (request, timeout = 6000) => {
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

// Cache-First: статика, которая не меняется между запросами в рамках
// одной установленной версии SW. Сеть трогаем только если в кэше пусто,
// либо в фоне докачиваем свежую версию, не блокируя ответ.
const cacheFirst = (request) => {
  return caches.match(request, { ignoreVary: true }).then((cached) => {
    if (cached) {
      // Обновляем кэш в фоне, не дожидаясь ответа — пользователь получает
      // мгновенный ответ из кэша, а свежая версия подтянется к следующему разу.
      fetchWithTimeout(request)
        .then((response) => {
          if (response.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, response));
          }
        })
        .catch(() => {});
      return cached;
    }
    return fetchWithTimeout(request).then((response) => {
      if (response.status === 200) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    });
  });
};

// Online-First: если есть сеть — всегда идём за свежими данными к беку
// (и попутно обновляем кэш этим ответом). Если сети/бека нет —
// единственный источник ответа — кэш. Используется для HTML-навигации
// и всех API-запросов (/rating/, /students/), где важна актуальность данных.
const onlineFirst = (request) => {
  return fetchWithTimeout(request)
    .then((response) => {
      if (response.status === 200) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    })
    .catch(() => {
      return caches.match(request, { ignoreVary: true }).then((cachedResponse) => {
        if (cachedResponse) return cachedResponse;
        if (request.mode === "navigate") {
          return caches.match("./index.html", { ignoreVary: true });
        }
        return new Response(JSON.stringify({ error: "Offline and no cache" }), {
          status: 504,
          statusText: "Gateway Timeout",
          headers: { "Content-Type": "application/json" }
        });
      });
    });
};

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;

  const isStatic = STATIC_EXTENSIONS.test(e.request.url);

  e.respondWith(isStatic ? cacheFirst(e.request) : onlineFirst(e.request));
});
