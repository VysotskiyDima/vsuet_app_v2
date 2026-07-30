/**
 * Вход в зачётку и выход из неё — переключение между экраном входа и приложением.
 *
 * Номер зачётки здесь единственное состояние «входа»: пока он запомнен,
 * сессия считается открытой и переживает перезагрузку страницы.
 */

import { $ } from "./utils.js";
import { clearZach, getZach, savedZach, setZach } from "./store.js";
import { invalidateSchedule, switchTab } from "./nav.js";
import { clearRating, loadRating } from "./view-rating.js";
import { focusZachInput, resetLoginForm } from "./login.js";
import { resetSchedule } from "./view-schedule.js";

const viewLogin = $("#view-login");
const viewApp = $("#view-app");

export function openApp(zach) {
  setZach(zach);
  viewLogin.hidden = true;
  viewApp.hidden = false;
  invalidateSchedule();
  resetSchedule();
  switchTab("rating");
  loadRating(zach);
}

export function closeApp() {
  clearZach();
  viewApp.hidden = true;
  viewLogin.hidden = false;
  clearRating();
  resetLoginForm();
}

/**
 * Восстановление сессии при загрузке страницы.
 *
 * Если номер больше не действителен, loadRating покажет ошибку с повтором,
 * а «Выход» в тулбаре вернёт на экран входа и забудет номер.
 */
export function restoreSession() {
  const zach = savedZach();
  if (zach) {
    openApp(zach);
    return true;
  }
  // Расставляем hidden явно: сразу после этого main.js снимет data-boot,
  // и видимостью экранов будет управлять только он.
  viewApp.hidden = true;
  viewLogin.hidden = false;
  focusZachInput();
  return false;
}

export { getZach };
