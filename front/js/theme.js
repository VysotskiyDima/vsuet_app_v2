/**
 * Тема оформления.
 *
 * Сам атрибут data-theme на <html> выставляет инлайн-скрипт в <head>: он
 * обязан отработать до первой отрисовки, иначе на тёмной теме мигает светлый
 * фон. Здесь — переключение по требованию и синхронизация meta[theme-color].
 */

import { STORAGE_KEYS } from "./config.js";

// Держим в синхроне с --paper в css/tokens.css: этим цветом система красит
// адресную строку и статус-бар установленного PWA.
const THEME_COLORS = { light: "#E9EAE3", dark: "#14161A" };

const themeMeta = document.querySelector('meta[name="theme-color"]');

export function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function applyTheme(name) {
  document.documentElement.dataset.theme = name;
  syncThemeColor();
  try {
    localStorage.setItem(STORAGE_KEYS.theme, name);
  } catch (_) {
    /* приватный режим — тема не запомнится */
  }
}

/** Инлайн-скрипт выставил data-theme, но meta не трогал — догоняем. */
export function syncThemeColor() {
  if (themeMeta) themeMeta.setAttribute("content", THEME_COLORS[currentTheme()]);
}
