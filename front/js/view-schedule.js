/**
 * Экран расписания: выбор недели и дня, карточки пар.
 *
 * Данные тянет с бэкенда по группе студента (js/data/schedule.js). Группу
 * подгружает session.js при входе, поэтому здесь возможны три состояния:
 * группа ещё не пришла, у группы нет расписания, расписание есть.
 *
 * Разметку кладёт в #schedule-content, стили — css/schedule.css.
 */

import { $, escapeHtml, plural, sealSvg } from "./utils.js";
import { getGroup } from "./store.js";
import { DAYS, LESSON_TYPES, hasSubgroups, lessonCount, lessonsFor, loadSchedule } from "./data/schedule.js";

let schedWeek = "numerator";
let schedDay = null;
// 0 — показывать всё без деления; 1 или 2 — только своя подгруппа.
let schedSubgroup = 0;

function currentDayKey() {
  const js = new Date().getDay(); // 0=вс … 6=сб
  return DAYS[js >= 1 && js <= 6 ? js - 1 : 0].key; // Пн…Сб, в воскресенье открываем Пн
}

/** Экран состояния: загрузка, пусто, ошибка. */
function renderState(title, text, retry) {
  $("#schedule-content").innerHTML = `
    <div class="state">
      ${sealSvg}
      <h2 class="state__title">${escapeHtml(title)}</h2>
      <p class="state__text">${escapeHtml(text)}</p>
      ${retry ? '<button class="btn" type="button" id="sched-retry">Повторить</button>' : ""}
    </div>`;
  if (retry) $("#sched-retry").addEventListener("click", retry);
}

export async function renderSchedule() {
  const group = getGroup();

  // Группа приходит отдельным запросом на входе; без неё расписание не за что зацепить.
  if (group === undefined) {
    renderState("Загружаем расписание", "Определяем вашу группу…");
    return;
  }
  if (!group) {
    renderState("Группа не определена", "Расписание привязано к группе, а её пока нет в базе.");
    return;
  }

  let schedule;
  try {
    schedule = await loadSchedule(group);
  } catch (_) {
    renderState("Не удалось загрузить расписание", "Сервер недоступен или вернул ошибку.", renderSchedule);
    return;
  }

  if (!schedule) {
    renderState("Расписания пока нет", `Для группы ${group} расписание ещё не загружено.`);
    return;
  }

  if (!schedDay) schedDay = currentDayKey();

  const el = $("#schedule-content");
  el.innerHTML = `
    <div class="sched">
      <div class="sched__head">
        <div class="seg" role="group" aria-label="Тип недели">
          <button class="seg__btn ${schedWeek === "numerator" ? "is-active" : ""}" type="button" data-week="numerator">Числитель</button>
          <button class="seg__btn ${schedWeek === "denominator" ? "is-active" : ""}" type="button" data-week="denominator">Знаменатель</button>
        </div>
        ${subgroupPicker(schedule)}
      </div>
      <div class="days" role="tablist" aria-label="День недели">
        ${DAYS.map((day) => {
          const cnt = lessonCount(schedule, schedWeek, day.key, schedSubgroup);
          return `<button class="day ${day.key === schedDay ? "is-active" : ""} ${cnt ? "" : "is-empty"}" type="button" data-day="${day.key}">
            <span class="day__dow">${day.short}</span>
            <span class="day__cnt">${cnt ? cnt + " " + plural(cnt, ["пара", "пары", "пар"]) : "—"}</span>
          </button>`;
        }).join("")}
      </div>
      <div id="sched-day"></div>
    </div>`;

  renderSchedDay(schedule);

  // Именно [data-week], а не .seg__btn: под общий класс попадают и кнопки
  // выбора подгруппы, у которых своего data-week нет.
  el.querySelectorAll("[data-week]").forEach((b) =>
    b.addEventListener("click", () => {
      schedWeek = b.dataset.week;
      renderSchedule();
    }),
  );
  el.querySelectorAll(".day").forEach((b) =>
    b.addEventListener("click", () => {
      schedDay = b.dataset.day;
      el.querySelectorAll(".day").forEach((x) => x.classList.toggle("is-active", x === b));
      renderSchedDay(schedule);
    }),
  );
  el.querySelectorAll("[data-subgroup]").forEach((b) =>
    b.addEventListener("click", () => {
      schedSubgroup = Number(b.dataset.subgroup);
      renderSchedule();
    }),
  );
}

/**
 * Селект подгруппы. По умолчанию «Все» — расписание показывается целиком,
 * как будто деления нет. Для групп без подгрупп не рисуется вовсе.
 */
function subgroupPicker(schedule) {
  if (!hasSubgroups(schedule)) return "";
  const option = (value, label) =>
    `<button class="seg__btn ${schedSubgroup === value ? "is-active" : ""}" type="button" data-subgroup="${value}">${label}</button>`;
  return `
    <div class="sched__pick">
      <span class="sched__pick-label" id="subgroup-label">Подгруппа</span>
      <div class="seg seg--compact" role="group" aria-labelledby="subgroup-label">
        ${option(0, "Все")}${option(1, "1")}${option(2, "2")}
      </div>
    </div>`;
}

function renderSchedDay(schedule) {
  const wrap = $("#sched-day");
  const lessons = lessonsFor(schedule, schedWeek, schedDay, schedSubgroup);
  const day = DAYS.find((d) => d.key === schedDay);
  const weekLabel = schedWeek === "numerator" ? "Числитель" : "Знаменатель";

  let html = `
    <div class="sched__meta">
      <h2 class="sched__day-title">${escapeHtml(day.title)}</h2>
      <span class="sched__week-tag">${weekLabel}</span>
    </div>`;

  if (!lessons.length) {
    html += `<div class="sched-empty">
      <svg class="sched-empty__seal" viewBox="0 0 200 200" aria-hidden="true"><use href="#seal-mini"/></svg>
      <div>В этот день занятий нет</div>
    </div>`;
  } else {
    html += `<div class="sched-list">${lessons.map(lessonCard).join("")}</div>`;
  }
  wrap.innerHTML = html;
}

function lessonCard(lesson) {
  const row = (label, value, code) =>
    value
      ? `<div class="sched-card__row"><dt>${label}</dt><dd${code ? ' class="is-code"' : ""}>${escapeHtml(value)}</dd></div>`
      : "";

  // Подгруппу показываем, только когда занятие идёт не всей группе:
  // [1, 2] означает «все», и уточнять там нечего.
  const split = Array.isArray(lesson.subgroup) && lesson.subgroup.length === 1;

  return `<article class="sched-card" data-type="${escapeHtml(lesson.type)}">
    <div class="sched-card__time">${escapeHtml(lesson.start)}<span>${escapeHtml(lesson.endTime || "")}</span></div>
    <div class="sched-card__body">
      <div class="sched-card__name">${escapeHtml(lesson.name)}</div>
      <dl class="sched-card__meta">
        ${row("Ауд.", lesson.classroom, true)}
        ${row("Преподаватель", lesson.teacherName)}
        ${split ? row("№ подгруппы", String(lesson.subgroup[0]), true) : ""}
      </dl>
    </div>
    <span class="sched-card__badge">${LESSON_TYPES[lesson.type] || "Занятие"}</span>
  </article>`;
}

/** Сброс при новом входе: текущий день и показ без фильтра по подгруппе. */
export function resetSchedule() {
  schedDay = null;
  schedSubgroup = 0;
}
