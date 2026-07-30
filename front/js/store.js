/**
 * Состояние сессии: чей рейтинг сейчас открыт.
 *
 * Вынесено отдельным модулем без импортов намеренно. Номер зачётки нужен и
 * экрану настроек, и экрану рейтинга, и логике входа. Если бы его хранил
 * session.js, получилось бы кольцо импортов: session → nav → settings → session.
 */

import { STORAGE_KEYS } from "./config.js";

let currentZach = "";

export function getZach() {
  return currentZach;
}

/** Запоминает номер и в памяти, и на диске: сессия должна пережить перезагрузку. */
export function setZach(zach) {
  currentZach = zach;
  try {
    localStorage.setItem(STORAGE_KEYS.zach, zach);
  } catch (_) {
    /* приватный режим — работаем без сохранения */
  }
}

export function clearZach() {
  currentZach = "";
  try {
    localStorage.removeItem(STORAGE_KEYS.zach);
  } catch (_) {
    /* см. выше */
  }
}

/** Номер из прошлой сессии либо null. */
export function savedZach() {
  try {
    return localStorage.getItem(STORAGE_KEYS.zach);
  } catch (_) {
    return null;
  }
}
