/**
 * Тулбар и переключение разделов.
 *
 * Один и тот же тулбар — сайдбар на десктопе и нижняя панель на мобилке;
 * разница целиком в css/app-shell.css, разметка и логика общие.
 *
 * Кнопка выхода живёт в тулбаре, но разделом не является: у неё нет data-tab,
 * а обработчик приходит колбэком из main.js — иначе nav зависел бы от session.
 */

import { $ } from "./utils.js";
import { renderSchedule } from "./view-schedule.js";
import { renderSettings } from "./view-settings.js";

const navItems = document.querySelectorAll(".nav__item[data-tab]");
const panels = document.querySelectorAll(".tab");

// Расписание не меняется между переключениями — рисуем один раз за сессию.
let scheduleRendered = false;

export function switchTab(name) {
  navItems.forEach((b) => {
    const active = b.dataset.tab === name;
    b.classList.toggle("is-active", active);
    if (active) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });

  panels.forEach((s) => {
    s.hidden = s.dataset.panel !== name;
  });
  window.scrollTo(0, 0);

  if (name === "schedule" && !scheduleRendered) {
    renderSchedule();
    scheduleRendered = true;
  }
  if (name === "settings") renderSettings();
}

/** Заставить расписание перерисоваться при следующем открытии вкладки. */
export function invalidateSchedule() {
  scheduleRendered = false;
}

export function initNav({ onLogout }) {
  navItems.forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#logout-btn").addEventListener("click", onLogout);
}
