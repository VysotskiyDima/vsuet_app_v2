/**
 * Экран расписания: выбор недели и дня, карточки пар.
 *
 * Данные берёт из js/data/mock-schedule.js — заменить источник можно, не
 * трогая отрисовку. Разметку кладёт в #schedule-content, стили — css/schedule.css.
 */

import { $, escapeHtml, plural } from "./utils.js";
import {
  LESSON_TYPES,
  MOCK_SCHEDULE,
  SCHED_DAYS,
  SCHED_DOW_SHORT,
} from "./data/mock-schedule.js";

let schedWeek = "numerator"; // числитель/знаменатель — данные пока одинаковы
let schedDay = null;

function currentDowIndex() {
  const js = new Date().getDay(); // 0=вс … 6=сб
  return (js >= 1 && js <= 6) ? js - 1 : 0; // Пн…Сб, в воскресенье открываем Пн
}

export function renderSchedule() {
  if (!schedDay) schedDay = SCHED_DAYS[currentDowIndex()];
  const el = $("#schedule-content");
  el.innerHTML = `
    <div class="sched">
      <div class="sched__head">
        <div class="seg" role="group" aria-label="Тип недели">
          <button class="seg__btn ${schedWeek === "numerator" ? "is-active" : ""}" type="button" data-week="numerator">Числитель</button>
          <button class="seg__btn ${schedWeek === "denominator" ? "is-active" : ""}" type="button" data-week="denominator">Знаменатель</button>
        </div>
      </div>
      <div class="days" role="tablist" aria-label="День недели">
        ${SCHED_DAYS.map((d) => {
          const cnt = (MOCK_SCHEDULE[d] || []).length;
          return `<button class="day ${d === schedDay ? "is-active" : ""} ${cnt ? "" : "is-empty"}" type="button" data-day="${d}">
            <span class="day__dow">${SCHED_DOW_SHORT[d]}</span>
            <span class="day__cnt">${cnt ? cnt + " " + plural(cnt, ["пара", "пары", "пар"]) : "—"}</span>
          </button>`;
        }).join("")}
      </div>
      <div id="sched-day"></div>
    </div>`;
  renderSchedDay();

  el.querySelectorAll(".seg__btn").forEach((b) =>
    b.addEventListener("click", () => { schedWeek = b.dataset.week; renderSchedule(); })
  );
  el.querySelectorAll(".day").forEach((b) =>
    b.addEventListener("click", () => {
      schedDay = b.dataset.day;
      el.querySelectorAll(".day").forEach((x) => x.classList.toggle("is-active", x === b));
      renderSchedDay();
    })
  );
}

function renderSchedDay() {
  const wrap = $("#sched-day");
  const lessons = MOCK_SCHEDULE[schedDay] || [];
  const dowFull = schedDay.charAt(0) + schedDay.slice(1).toLowerCase();
  const weekLabel = schedWeek === "numerator" ? "Числитель" : "Знаменатель";

  let html = `
    <div class="sched__meta">
      <h2 class="sched__day-title">${dowFull}</h2>
      <span class="sched__week-tag">${weekLabel}</span>
    </div>`;

  if (!lessons.length) {
    html += `<div class="sched-empty">
      <svg class="sched-empty__seal" viewBox="0 0 200 200" aria-hidden="true"><use href="#seal-mini"/></svg>
      <div>В этот день занятий нет</div>
    </div>`;
  } else {
    html += `<div class="sched-list">${lessons.map((l) => {
      const [start, end] = l.time.split("-");
      const teacher = l.teacher
        ? `<div class="sched-card__row"><dt>Преподаватель</dt><dd>${escapeHtml(l.teacher)}</dd></div>`
        : "";
      // Подгруппа есть не у всех: лекции и семинары идут всем потоком.
      const subgroup = l.subgroup
        ? `<div class="sched-card__row"><dt>№ подгруппы</dt><dd class="is-code">${escapeHtml(l.subgroup)}</dd></div>`
        : "";
      return `<article class="sched-card" data-type="${l.type}">
        <div class="sched-card__time">${escapeHtml(start)}<span>${escapeHtml(end)}</span></div>
        <div class="sched-card__body">
          <div class="sched-card__name">${escapeHtml(l.name)}</div>
          <dl class="sched-card__meta">
            <div class="sched-card__row"><dt>Ауд.</dt><dd class="is-code">${escapeHtml(l.room)}</dd></div>
            ${teacher}
            ${subgroup}
          </dl>
        </div>
        <span class="sched-card__badge">${LESSON_TYPES[l.type] || "Другое"}</span>
      </article>`;
    }).join("")}</div>`;
  }
  wrap.innerHTML = html;
}

/** Сброс при новом входе, чтобы следующий показ начался с текущего дня. */
export function resetSchedule() {
  schedDay = null;
}
