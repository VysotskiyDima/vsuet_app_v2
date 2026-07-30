/** Регистрация service worker (офлайн-режим и установка как PWA). */

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("./sw.js")
      .then((reg) => {
        console.log("Service Worker зарегистрирован:", reg.scope);
        // Проверяем обновление на каждой загрузке — иначе новая версия
        // подхватится только после закрытия всех вкладок.
        reg.update();
      })
      .catch((err) => console.error("Ошибка регистрации Service Worker:", err));
  });

  // Новый worker забрал управление — перезагружаемся, чтобы страница и скрипты
  // были из одной версии. Флаг защищает от цикла перезагрузок.
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });
}
