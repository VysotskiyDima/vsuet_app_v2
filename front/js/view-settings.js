/**
 * Экран настроек: карточка профиля и выбор темы.
 *
 * Перерисовывается целиком при каждом открытии вкладки и после смены темы —
 * состояния тут нет, всё берётся из store и theme.
 */

import { $, escapeHtml } from "./utils.js";
import { getZach } from "./store.js";
import { applyTheme, currentTheme } from "./theme.js";
import { MOCK_GROUP } from "./data/mock-schedule.js";

export function renderSettings() {
  const el = $("#settings-content");
  const theme = currentTheme();

  el.innerHTML = `
    <div class="settings">
      <div class="set-card">
        <p class="set-card__label">Профиль</p>
        <div class="set-list">
          <div class="set-row">
            <span class="set-row__k">Зачётная книжка</span>
            <span class="set-row__v set-row__v--code">№ ${escapeHtml(getZach() || "—")}</span>
          </div>
          <div class="set-row">
            <span class="set-row__k">Группа</span>
            <span class="set-row__v set-row__v--code">${escapeHtml(MOCK_GROUP)}</span>
          </div>
        </div>
      </div>

      <div class="set-card">
        <p class="set-card__label">Оформление</p>
        <div class="set-row set-row--control">
          <span class="set-row__k">Тема</span>
          <div class="seg" role="group" aria-label="Тема оформления">
            <button class="seg__btn ${theme === "light" ? "is-active" : ""}" type="button" data-set-theme="light">Светлая</button>
            <button class="seg__btn ${theme === "dark" ? "is-active" : ""}" type="button" data-set-theme="dark">Тёмная</button>
          </div>
        </div>
      </div>
    </div>`;

  el.querySelectorAll("[data-set-theme]").forEach((b) =>
    b.addEventListener("click", () => {
      applyTheme(b.dataset.setTheme);
      renderSettings();
    }),
  );
}
