/**
 * Точка входа. Здесь и только здесь модули связываются друг с другом.
 *
 * Экраны и тулбар не импортируют сессию напрямую, а принимают колбэки —
 * иначе импорты замкнулись бы в кольцо (login → session → login,
 * nav → session → nav). Вся проводка собрана в одном месте, ниже.
 *
 * Порядок в разметке: этот модуль подключён как type="module", то есть
 * выполняется после разбора HTML. Чтобы экран входа не мелькал у тех, кто уже
 * вошёл, инлайн-скрипт в <head> заранее помечает <html> атрибутом
 * data-boot — по нему CSS прячет ненужный экран до старта модулей.
 */

import "./kt-popup.js"; // сам подписывается на клики по ячейкам КТ
import { initLogin } from "./login.js";
import { initNav } from "./nav.js";
import { closeApp, openApp, restoreSession } from "./session.js";
import { registerServiceWorker } from "./sw-register.js";
import { syncThemeColor } from "./theme.js";

syncThemeColor();

initLogin({ onSuccess: openApp });
initNav({ onLogout: closeApp });

restoreSession();

// Модули отработали и сами управляют видимостью экранов — подсказка для
// первой отрисовки больше не нужна, иначе она перекрыла бы смену экрана.
document.documentElement.removeAttribute("data-boot");

registerServiceWorker();
