/* ============================================================
   Рейтинг успеваемости — клиентская логика (без зависимостей)
   ============================================================ */

"use strict";

const API_BASE =
  window.location.port === "3000"
    ? `http://${window.location.hostname}:8000`
    : "";

const VED_TYPES = [
  { segment: "zachet",            title: "Зачёт",              kind: "rating" },
  { segment: "ekzamen",           title: "Экзамен",            kind: "rating" },
  { segment: "vypusknaya-rabota", title: "Выпускная работа",   kind: "grade"  },
  { segment: "gosekzamen",        title: "ГосЭкзамен",         kind: "grade"  },
  { segment: "kontrolnaya-rabota",title: "Контрольная работа", kind: "grade"  },
  { segment: "kursovaya-rabota",  title: "Курсовая работа",    kind: "grade"  },
  { segment: "kursovoy-proekt",   title: "Курсовой проект",    kind: "grade"  },
  { segment: "praktika",          title: "Практика",           kind: "grade"  },
];

const WORK_LABELS = { lecture: "Лекции", practice: "Практика", lab: "Лаб. работы", other: "Другое" };
const DASH = "—";

// ---- элементы ----
const $ = (sel, root = document) => root.querySelector(sel);
const viewLogin     = $("#view-login");
const viewApp       = $("#view-app");
const loginForm     = $("#login-form");
const zachInput     = $("#zach");
const loginBtn      = $("#login-btn");
const loginError    = $("#login-error");
const demoFill      = $("#demo-fill");
const currentZach   = $("#current-zach");
const currentZachM  = $("#current-zach-m");
const ratingContent = $("#rating-content");
let currentZachValue = "";

// ============================================================
// Утилиты
// ============================================================
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function plural(n, forms) {
  const n10 = n % 10, n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}
const disciplines = (n) => `${n} ${plural(n, ["дисциплина", "дисциплины", "дисциплин"])}`;

function isBlank(v) { return v === null || v === undefined || v === "-" || v === ""; }
function isZeroWeight(v) { return v === 0 || v === "0" || v === 0.0; }
function showNum(v) { return isBlank(v) ? DASH : escapeHtml(v); }

function gradeClass(grade) {
  switch (String(grade).trim()) {
    case "Отл":
    case "Зачтено":    return "is-good";
    case "Хор":        return "is-ok";
    case "Удовл":      return "is-mid";
    case "Неуд":
    case "Не зачтено": return "is-bad";
    default:           return "is-none";
  }
}

function isRatingRecord(rec) { return rec && Array.isArray(rec.control_points); }

const sealSvg = '<svg class="state__seal" viewBox="0 0 200 200" aria-hidden="true"><use href="#seal-mini"/></svg>';

// ============================================================
// Сеть
// ============================================================
async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ============================================================
// ВХОД
// ============================================================
function setLoginError(message) {
  if (!message) { loginError.hidden = true; loginError.textContent = ""; return; }
  loginError.hidden = false;
  loginError.textContent = message;
}

function setLoginLoading(loading) {
  loginBtn.disabled = loading;
  loginBtn.textContent = loading ? "Открываем…" : "Открыть";
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  setLoginError("");
  const zach = zachInput.value.replace(/\D/g, "").trim();
  if (!zach) { setLoginError("Введите номер зачётной книжки."); zachInput.focus(); return; }
  setLoginLoading(true);
  try {
    const data = await apiGet(`/students/${encodeURIComponent(zach)}/exists`);
    if (data && data.exists) { openRating(zach); }
    else { setLoginError(`Зачётная книжка № ${zach} не найдена. Проверьте номер.`); }
  } catch (err) {
    setLoginError("Не удалось связаться с сервером. Проверьте соединение.");
  } finally {
    setLoginLoading(false);
  }
});

zachInput.addEventListener("input", () => {
  const cleaned = zachInput.value.replace(/\D/g, "");
  if (cleaned !== zachInput.value) zachInput.value = cleaned;
  if (!loginError.hidden) setLoginError("");
});

if (demoFill) demoFill.addEventListener("click", () => { zachInput.value = "247162"; zachInput.focus(); });

// ============================================================
// Переключение экранов
// ============================================================
const LAST_ZACH_KEY = "rating:lastZach";
function rememberZach(zach) { try { localStorage.setItem(LAST_ZACH_KEY, zach); } catch (_) {} }

function openRating(zach) {
  currentZachValue = zach;
  currentZach.textContent = zach;
  if (currentZachM) currentZachM.textContent = zach;
  rememberZach(zach);
  viewLogin.hidden = true;
  viewApp.hidden = false;
  scheduleRendered = false;
  switchTab("rating");
  loadRating(zach);
}

function closeRating() {
  viewApp.hidden = true;
  viewLogin.hidden = false;
  ratingContent.innerHTML = "";
  zachInput.focus();
  zachInput.select();
}

// ============================================================
// Вкладки: Рейтинг / Расписание / Настройки
// ============================================================
const TAB_TITLES = { rating: "Рейтинг", schedule: "Расписание", settings: "Настройки" };
// Кнопка выхода тоже живёт в тулбаре, но разделом не является — берём только вкладки.
const navItems = document.querySelectorAll(".nav__item[data-tab]");
const tabTitle = $("#tab-title");
const tabTag = $("#tab-tag");
let scheduleRendered = false;

function switchTab(name) {
  navItems.forEach((b) => {
    const active = b.dataset.tab === name;
    b.classList.toggle("is-active", active);
    if (active) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.dataset.panel !== name; });
  if (tabTitle) tabTitle.textContent = TAB_TITLES[name] || "";
  // Подпись рядом с названием раздела: для расписания — группа.
  if (tabTag) {
    tabTag.textContent = name === "schedule" ? MOCK_GROUP : "";
    tabTag.hidden = name !== "schedule";
  }
  window.scrollTo(0, 0);

  if (name === "schedule" && !scheduleRendered) { renderSchedule(); scheduleRendered = true; }
  if (name === "settings") { renderSettings(); }
}

navItems.forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
$("#logout-btn").addEventListener("click", closeRating);

// ============================================================
// Расписание (моковые данные — одинаковы для числителя и знаменателя,
// и пока одинаковы для всех пользователей)
// ============================================================
const SCHED_DAYS = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА"];
const SCHED_DOW_SHORT = { "ПОНЕДЕЛЬНИК": "Пн", "ВТОРНИК": "Вт", "СРЕДА": "Ср", "ЧЕТВЕРГ": "Чт", "ПЯТНИЦА": "Пт", "СУББОТА": "Сб" };
const LESSON_TYPES = { lecture: "Лекция", practice: "Практика", lab: "Лаб. работа", seminar: "Семинар" };

const MOCK_GROUP = "ПИ-231";
const MOCK_SCHEDULE = {
  "ПОНЕДЕЛЬНИК": [
    { time: "08.00-09.35", name: "Математический анализ",       type: "lecture",  room: "К-301", teacher: "Иванова Т. С." },
    { time: "09.45-11.20", name: "Программирование на Python",  type: "lab",      room: "А-215", teacher: "Петров А. В." },
    { time: "11.50-13.25", name: "Дискретная математика",       type: "practice", room: "К-118", teacher: "Сидорова Е. Н." },
  ],
  "ВТОРНИК": [
    { time: "09.45-11.20", name: "Базы данных",                 type: "lecture",  room: "К-204", teacher: "Кузнецов Д. И." },
    { time: "11.50-13.25", name: "Базы данных",                 type: "lab",      room: "А-217", teacher: "Кузнецов Д. И." },
    { time: "13.35-15.10", name: "Иностранный язык",            type: "seminar",  room: "Г-402", teacher: "Морозова И. П." },
  ],
  "СРЕДА": [
    { time: "08.00-09.35", name: "Операционные системы",        type: "lecture",  room: "К-301", teacher: "Фёдоров С. А." },
    { time: "09.45-11.20", name: "Операционные системы",        type: "practice", room: "А-215", teacher: "Фёдоров С. А." },
    { time: "11.50-13.25", name: "Физическая культура",         type: "practice", room: "Спорткомплекс", teacher: "" },
    { time: "13.35-15.10", name: "Философия",                   type: "lecture",  room: "Г-210", teacher: "Волкова Н. М." },
  ],
  "ЧЕТВЕРГ": [
    { time: "09.45-11.20", name: "Веб-технологии",              type: "lab",      room: "А-219", teacher: "Николаев П. Р." },
    { time: "11.50-13.25", name: "Компьютерные сети",           type: "lecture",  room: "К-204", teacher: "Егоров В. Л." },
  ],
  "ПЯТНИЦА": [
    { time: "08.00-09.35", name: "Теория вероятностей",         type: "lecture",  room: "К-301", teacher: "Иванова Т. С." },
    { time: "09.45-11.20", name: "Теория вероятностей",         type: "practice", room: "К-118", teacher: "Иванова Т. С." },
    { time: "11.50-13.25", name: "Программная инженерия",       type: "seminar",  room: "А-215", teacher: "Петров А. В." },
  ],
  "СУББОТА": [
    { time: "09.45-11.20", name: "Архитектура ЭВМ",             type: "lecture",  room: "К-204", teacher: "Егоров В. Л." },
    { time: "11.50-13.25", name: "Веб-технологии",              type: "practice", room: "А-219", teacher: "Николаев П. Р." },
  ],
};

let schedWeek = "numerator"; // числитель/знаменатель — данные пока одинаковы
let schedDay = null;

function currentDowIndex() {
  const js = new Date().getDay(); // 0=вс … 6=сб
  return (js >= 1 && js <= 6) ? js - 1 : 0; // Пн…Сб, в воскресенье открываем Пн
}

function renderSchedule() {
  if (!schedDay) schedDay = SCHED_DAYS[currentDowIndex()];
  const el = $("#schedule-content");
  el.innerHTML = `
    <div class="sched">
      <div class="seg" role="group" aria-label="Тип недели">
        <button class="seg__btn ${schedWeek === "numerator" ? "is-active" : ""}" type="button" data-week="numerator">Числитель</button>
        <button class="seg__btn ${schedWeek === "denominator" ? "is-active" : ""}" type="button" data-week="denominator">Знаменатель</button>
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
      return `<article class="sched-card" data-type="${l.type}">
        <div class="sched-card__time">${escapeHtml(start)}<span>${escapeHtml(end)}</span></div>
        <div class="sched-card__body">
          <div class="sched-card__name">${escapeHtml(l.name)}</div>
          <dl class="sched-card__meta">
            <div class="sched-card__row"><dt>Ауд.</dt><dd class="is-code">${escapeHtml(l.room)}</dd></div>
            ${teacher}
          </dl>
        </div>
        <span class="sched-card__badge">${LESSON_TYPES[l.type] || "Другое"}</span>
      </article>`;
    }).join("")}</div>`;
  }
  wrap.innerHTML = html;
}

// ============================================================
// Настройки: профиль + место под доп. информацию
// ============================================================
function renderSettings() {
  const el = $("#settings-content");
  el.innerHTML = `
    <div class="settings">
      <div class="set-card">
        <div class="set-profile">
          <svg class="set-profile__seal" viewBox="0 0 200 200" aria-hidden="true"><use href="#seal-mini"/></svg>
          <div>
            <div class="set-profile__zach">№ ${escapeHtml(currentZachValue || "—")}</div>
            <div class="set-profile__sub">Зачётная книжка</div>
          </div>
        </div>
      </div>

      <div class="set-card">
        <p class="set-card__label">Профиль</p>
        <div class="set-list">
          <div class="set-row"><span class="set-row__k">Группа</span><span class="set-row__v set-row__v--soon">появится позже</span></div>
          <div class="set-row"><span class="set-row__k">ФИО</span><span class="set-row__v set-row__v--soon">появится позже</span></div>
          <div class="set-row"><span class="set-row__k">Уведомления об изменении рейтинга</span><span class="set-row__v set-row__v--soon">появится позже</span></div>
        </div>
      </div>

      <p class="set-about">Рейтинг <b>успеваемости</b> · ВГУИТ</p>
    </div>`;
}

// ============================================================
// Загрузка и отрисовка рейтинга
// ============================================================
function renderState(kind, title, text, retry) {
  const cls = kind === "loading" ? "state loading" : "state";
  ratingContent.innerHTML = `
    <div class="${cls}">
      ${sealSvg}
      <h2 class="state__title">${escapeHtml(title)}</h2>
      <p class="state__text">${escapeHtml(text)}</p>
      ${retry ? '<button class="btn" type="button" id="state-retry">Повторить</button>' : ""}
    </div>`;
  if (retry) $("#state-retry").addEventListener("click", retry);
}

async function loadRating(zach) {
  renderState("loading", "Открываем зачётную книжку", `№ ${zach} · собираем ведомости…`);

  const results = await Promise.allSettled(
    VED_TYPES.map((t) => apiGet(`/rating/${encodeURIComponent(zach)}/${t.segment}`))
  );

  const sections = [];
  let failed = 0;
  results.forEach((res, i) => {
    if (res.status === "fulfilled") {
      const records = Array.isArray(res.value) ? res.value : [];
      if (records.length) sections.push({ type: VED_TYPES[i], records });
    } else { failed += 1; }
  });

  if (failed === VED_TYPES.length) {
    renderState("error", "Не удалось загрузить данные", "Сервер недоступен или вернул ошибку.", () => loadRating(zach));
    return;
  }
  if (sections.length === 0) {
    renderState("empty", "Ведомостей пока нет", `По зачётной книжке № ${zach} данные об успеваемости отсутствуют.`);
    return;
  }

  let html = "";
  if (failed > 0) {
    html += `
      <div class="banner" role="status">
        <span>Некоторые разделы не загрузились (${failed}).</span>
        <button class="btn btn--ghost banner__retry" type="button" id="banner-retry">Повторить</button>
      </div>`;
  }
  html += sections.map((s, idx) => renderSection(s, idx)).join("");
  ratingContent.innerHTML = html;

  const bannerRetry = $("#banner-retry");
  if (bannerRetry) bannerRetry.addEventListener("click", () => loadRating(zach));
}

function renderSection(section, index) {
  const { type, records } = section;
  const rating = isRatingRecord(records[0]);
  const table  = rating ? renderRatingTable(records) : renderGradeTable(records);

  return `
    <section class="section" style="animation-delay:${Math.min(index, 8) * 55}ms">
      <div class="section__head">
        <h2 class="section__title">${escapeHtml(type.title)}</h2>
        <span class="section__count">${disciplines(records.length)}</span>
      </div>
      ${table}
    </section>`;
}

// ---- рейтинговая таблица со sticky-колонкой ----
function renderRatingTable(records) {
  const maxKt = records.reduce((m, r) => Math.max(m, (r.control_points || []).length), 0);

  // Заголовок: sticky-ячейка «Дисциплина» + КТ-колонки + «Рейтинг»
  let head = '<tr><th class="rt-subject">Дисциплина</th>';
  for (let k = 1; k <= maxKt; k++) {
    head += `<th class="kt-result">КТ ${k}</th>`;
  }
  head += '<th class="rt-final">Рейтинг</th></tr>';

  const body = records.map((rec) => {
    const cps = rec.control_points || [];
    // sticky-ячейка названия
    let row = `<td class="rt-subject">${escapeHtml(rec.subject_name)}</td>`;

    for (let k = 0; k < maxKt; k++) {
      const cp = cps[k];
      const total = cp ? showNum(cp.total) : DASH;
      const hasData = cp && !isBlank(cp.total);

      if (hasData) {
        const cpJson = escapeHtml(JSON.stringify(cp));
        row += `<td class="rt-total rt-total--clickable"
                    data-cp="${cpJson}"
                    data-kt="${k + 1}"
                    data-subject="${escapeHtml(rec.subject_name)}"
                    title="Нажмите для деталей"
                    tabindex="0"
                    role="button">${total}</td>`;
      } else {
        row += `<td class="rt-total">${total}</td>`;
      }
    }

    row += `<td class="rt-rating">${showNum(rec.final_rating)}</td>`;
    return `<tr>${row}</tr>`;
  }).join("");

  // rt-scroll — новая обёртка вместо table-scroll, содержит тени-подсказки
  return `
    <div class="rt-scroll">
      <table class="rt">
        <thead>${head}</thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="rt-caption">Нажмите на балл КТ, чтобы увидеть детализацию по видам работ.</p>`;
}

// ---- оценочная таблица ----
function renderGradeTable(records) {
  const rows = records.map((rec) => {
    const grade = isBlank(rec.grade) ? DASH : rec.grade;
    return `
      <tr>
        <td class="gt-subject">${escapeHtml(rec.subject_name)}</td>
        <td><span class="chip ${gradeClass(rec.grade)}">${escapeHtml(grade)}</span></td>
      </tr>`;
  }).join("");

  return `
    <div class="table-scroll">
      <table class="gt">
        <thead><tr><th>Дисциплина</th><th>Оценка</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ============================================================
// Попап детализации КТ
// ============================================================
const popupEl = document.createElement("div");
popupEl.id = "kt-popup";
popupEl.className = "kt-popup";
popupEl.setAttribute("role", "dialog");
popupEl.setAttribute("aria-modal", "true");
popupEl.setAttribute("aria-labelledby", "kt-popup-title");
popupEl.hidden = true;
popupEl.innerHTML = `
  <div class="kt-popup__backdrop"></div>
  <div class="kt-popup__box">
    <div class="kt-popup__handle"></div>
    <button class="kt-popup__close" type="button" aria-label="Закрыть">✕</button>
    <h3 class="kt-popup__title" id="kt-popup-title"></h3>
    <table class="kt-popup__table">
      <thead>
        <tr>
          <th class="kt-popup__col-name">Вид работы</th>
          <th class="kt-popup__col-weight">Вес</th>
          <th class="kt-popup__col-score">Балл</th>
        </tr>
      </thead>
      <tbody id="kt-popup-body"></tbody>
    </table>
    <div class="kt-popup__total" id="kt-popup-total"></div>
  </div>`;
document.body.appendChild(popupEl);

function openKtPopup(subject, ktNum, cp) {
  document.getElementById("kt-popup-title").textContent = `${subject} · КТ ${ktNum}`;

  const rows = Object.entries(WORK_LABELS)
    .filter(([key]) => {
      const w = cp[key];
      if (!w) return false;
      if (isBlank(w.weight) || isZeroWeight(w.weight)) return false;
      return true;
    })
    .map(([key, label]) => {
      const w = cp[key];
      const score  = !isBlank(w.score)  ? escapeHtml(String(w.score))  : DASH;
      const weight = `${escapeHtml(String(w.weight))}%`;
      return `<tr>
        <td class="kt-popup__col-name">${label}</td>
        <td class="kt-popup__col-weight">${weight}</td>
        <td class="kt-popup__col-score">${score}</td>
      </tr>`;
    }).join("");

  document.getElementById("kt-popup-body").innerHTML =
    rows || `<tr><td colspan="3" style="text-align:center;color:#aaa">Нет данных</td></tr>`;
  document.getElementById("kt-popup-total").innerHTML =
    `Итог КТ: <strong>${showNum(cp.total)}</strong>`;

  popupEl.hidden = false;
  // iOS игнорирует overflow:hidden на body — фиксируем страницу целиком
  scrollLockY = window.scrollY;
  document.body.style.position = "fixed";
  document.body.style.top = `-${scrollLockY}px`;
  document.body.style.width = "100%";
  document.body.style.overflow = "hidden";
  popupEl.querySelector(".kt-popup__close").focus();
}

function closeKtPopup() {
  popupEl.hidden = true;
  document.body.style.position = "";
  document.body.style.top = "";
  document.body.style.width = "";
  document.body.style.overflow = "";
  window.scrollTo(0, scrollLockY);
}

popupEl.querySelector(".kt-popup__close").addEventListener("click", closeKtPopup);
popupEl.querySelector(".kt-popup__backdrop").addEventListener("click", closeKtPopup);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeKtPopup(); });

// Свайп вниз для закрытия шторки на мобилке
let touchStartY = 0;
let touchCurrentY = 0;
let isDragging = false;
let scrollLockY = 0;
const popupBox = popupEl.querySelector(".kt-popup__box");

popupBox.addEventListener("touchstart", (e) => {
  if (popupBox.scrollTop <= 0) {
    touchStartY = e.touches[0].clientY;
    touchCurrentY = touchStartY;
    isDragging = true;
    popupBox.style.transition = "none";
  }
}, { passive: true });

popupBox.addEventListener("touchmove", (e) => {
  if (!isDragging) return;

  if (popupBox.scrollTop > 0) {
    isDragging = false;
    popupBox.style.transform = "";
    return;
  }

  touchCurrentY = e.touches[0].clientY;
  const deltaY = touchCurrentY - touchStartY;

  if (deltaY >= 0) {
    // preventDefault на первом же движении, иначе iOS заберёт жест под нативный скролл
    if (e.cancelable) e.preventDefault();
    popupBox.style.transform = deltaY > 0 ? `translateY(${deltaY}px)` : "";
  } else {
    popupBox.style.transform = "";
  }
}, { passive: false });

popupBox.addEventListener("touchend", () => {
  if (!isDragging) return;
  isDragging = false;

  const deltaY = touchCurrentY - touchStartY;
  popupBox.style.transition = "transform 0.22s cubic-bezier(0.2, 0.65, 0.25, 1)";

  if (deltaY > 100) {
    popupBox.style.transform = "translateY(100%)";
    setTimeout(() => {
      closeKtPopup();
      popupBox.style.transform = "";
    }, 200);
  } else {
    popupBox.style.transform = "";
  }

  touchStartY = 0;
  touchCurrentY = 0;
});

document.addEventListener("click", (e) => {
  const cell = e.target.closest(".rt-total--clickable");
  if (!cell) return;
  try {
    openKtPopup(cell.dataset.subject, cell.dataset.kt, JSON.parse(cell.dataset.cp));
  } catch (_) {}
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const cell = e.target.closest(".rt-total--clickable");
  if (!cell) return;
  e.preventDefault();
  cell.click();
});

// ============================================================
// Восстановление последнего номера
// ============================================================
try {
  const last = localStorage.getItem(LAST_ZACH_KEY);
  if (last) zachInput.value = last;
} catch (_) {}
zachInput.focus();
zachInput.select();

// ============================================================
// Регистрация Service Worker (PWA)
// ============================================================
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js")
      .then((reg) => {
        console.log("Service Worker зарегистрирован:", reg.scope);
        // Принудительно проверяем наличие обновлений при каждой загрузке страницы
        reg.update();
      })
      .catch((err) => console.error("Ошибка регистрации Service Worker:", err));
  });

  // Автоматически перезагружаем страницу, когда новый Service Worker активируется
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!refreshing) {
      refreshing = true;
      window.location.reload();
    }
  });
}
