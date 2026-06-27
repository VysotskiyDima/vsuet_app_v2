/* ============================================================
   ВГУИТ · Рейтинг успеваемости — клиентская логика (без зависимостей)
   ============================================================ */

"use strict";

// База API. CORS на бэкенде разрешает любой localhost-порт.
const API_BASE = "http://localhost:8000";

// Типы ведомостей в порядке отображения. kind — подсказка;
// фактический вид таблицы определяется по форме записи.
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

const WORK_LABELS = { lecture: "Лекции", practice: "Практика", lab: "Лаб.", other: "Другое" };
const DASH = "—";

// ---- элементы ----
const $ = (sel, root = document) => root.querySelector(sel);
const viewLogin   = $("#view-login");
const viewRating  = $("#view-rating");
const loginForm   = $("#login-form");
const zachInput   = $("#zach");
const loginBtn    = $("#login-btn");
const loginError  = $("#login-error");
const demoFill    = $("#demo-fill");
const currentZach = $("#current-zach");
const logoutBtn   = $("#logout-btn");
const ratingContent = $("#rating-content");

// ============================================================
// Утилиты
// ============================================================
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Русская плюрализация: forms = [1, 2-4, 5+]
function plural(n, forms) {
  const n10 = n % 10, n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}
const disciplines = (n) => `${n} ${plural(n, ["дисциплина", "дисциплины", "дисциплин"])}`;

// Значение балла: число → как есть, "-"/пусто → длинное тире.
function isBlank(v) {
  return v === null || v === undefined || v === "-" || v === "";
}
function showNum(v) {
  return isBlank(v) ? DASH : escapeHtml(v);
}

function gradeClass(grade) {
  switch (String(grade).trim()) {
    case "Отл":
    case "Зачтено": return "is-good";
    case "Хор": return "is-ok";
    case "Удовл": return "is-mid";
    case "Неуд":
    case "Не зачтено": return "is-bad";
    default: return "is-none";
  }
}

function isRatingRecord(rec) {
  return rec && Array.isArray(rec.control_points);
}

// Мини-печать для состояний (загрузка/пусто/ошибка).
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
  if (!message) {
    loginError.hidden = true;
    loginError.textContent = "";
    return;
  }
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
  if (!zach) {
    setLoginError("Введите номер зачётной книжки.");
    zachInput.focus();
    return;
  }

  setLoginLoading(true);
  try {
    const data = await apiGet(`/students/${encodeURIComponent(zach)}/exists`);
    if (data && data.exists) {
      openRating(zach);
    } else {
      setLoginError(`Зачётная книжка № ${zach} не найдена. Проверьте номер.`);
    }
  } catch (err) {
    setLoginError("Не удалось связаться с сервером. Проверьте, что бэкенд запущен на localhost:8000.");
  } finally {
    setLoginLoading(false);
  }
});

// разрешаем вводить только цифры
zachInput.addEventListener("input", () => {
  const cleaned = zachInput.value.replace(/\D/g, "");
  if (cleaned !== zachInput.value) zachInput.value = cleaned;
  if (!loginError.hidden) setLoginError("");
});

demoFill.addEventListener("click", () => {
  zachInput.value = "247162";
  zachInput.focus();
});

logoutBtn.addEventListener("click", closeRating);

// ============================================================
// Переключение экранов
// ============================================================
const LAST_ZACH_KEY = "vsuet:lastZach";

function rememberZach(zach) {
  try { localStorage.setItem(LAST_ZACH_KEY, zach); } catch (_) { /* приватный режим */ }
}

function openRating(zach) {
  currentZach.textContent = zach;
  rememberZach(zach);
  viewLogin.hidden = true;
  viewRating.hidden = false;
  window.scrollTo(0, 0);
  loadRating(zach);
}

function closeRating() {
  viewRating.hidden = true;
  viewLogin.hidden = false;
  ratingContent.innerHTML = "";
  zachInput.focus();
  zachInput.select();
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
    } else {
      failed += 1;
    }
  });

  // всё упало — общая ошибка
  if (failed === VED_TYPES.length) {
    renderState("error", "Не удалось загрузить данные", "Сервер недоступен или вернул ошибку.", () => loadRating(zach));
    return;
  }

  // ничего не нашли
  if (sections.length === 0) {
    renderState("empty", "Ведомостей пока нет", `По зачётной книжке № ${zach} данные об успеваемости отсутствуют.`);
    return;
  }

  // частичный успех — рисуем что есть
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
  const table = rating ? renderRatingTable(records) : renderGradeTable(records);
  const tag = rating
    ? '<span class="section__tag">Рейтинг · КТ</span>'
    : '<span class="section__tag section__tag--grade">Итоговая оценка</span>';

  return `
    <section class="section" style="animation-delay:${Math.min(index, 8) * 55}ms">
      <div class="section__head">
        <h2 class="section__title">${escapeHtml(type.title)}</h2>
        <span class="section__count">${disciplines(records.length)}</span>
        ${tag}
      </div>
      ${table}
    </section>`;
}

// ---- рейтинговая таблица (контрольные точки) ----
function renderRatingTable(records) {
  const maxKt = records.reduce((m, r) => Math.max(m, (r.control_points || []).length), 0);
  const works = ["lecture", "practice", "lab", "other"];
  // вес каждой КТ в итоговом рейтинге одинаков: 100% / число КТ (при 5 точках — 20%)
  const ktWeight = maxKt ? Math.round(100 / maxKt) : 0;

  // шапка: 2 уровня
  let head1 = '<tr><th class="rt-subject" rowspan="2">Дисциплина</th>';
  let head2 = "<tr>";
  for (let k = 1; k <= maxKt; k++) {
    head1 += `<th class="kt-group" colspan="${works.length}">КТ ${k}<span class="kt-group__w">вес ${ktWeight}%</span></th>`;
    head1 += `<th class="kt-result" rowspan="2">Итог<br>КТ ${k}</th>`;
    head2 += works.map((w) => `<th>${WORK_LABELS[w]}</th>`).join("");
  }
  head1 += '<th class="rt-final" rowspan="2">Рейтинг</th></tr>';
  head2 += "</tr>";

  // тело: строка = предмет
  const body = records.map((rec) => {
    const cps = rec.control_points || [];
    let row = `<td class="rt-subject">${escapeHtml(rec.subject_name)}</td>`;
    for (let k = 0; k < maxKt; k++) {
      const cp = cps[k];
      if (!cp) {
        row += works.map(() => '<td><span class="rt-cell is-empty"><span class="rt-cell__v">—</span></span></td>').join("");
        row += '<td class="rt-total">—</td>';
        continue;
      }
      row += works.map((w) => ratingCell(cp[w])).join("");
      row += `<td class="rt-total">${showNum(cp.total)}</td>`;
    }
    row += `<td class="rt-rating">${showNum(rec.final_rating)}</td>`;
    return `<tr>${row}</tr>`;
  }).join("");

  return `
    <div class="table-scroll">
      <table class="rt">
        <thead>${head1}${head2}</thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="rt-caption">Под баллом — вес вида работы внутри КТ. «Вес» рядом с КТ — её доля в итоговом рейтинге (все КТ равны).</p>`;
}

function ratingCell(work) {
  const score = work ? work.score : "-";
  const weight = work ? work.weight : "-";
  const blank = isBlank(score);
  // вес показываем только у оценённых работ — иначе под прочерком висит «0%»
  const w = blank || isBlank(weight) ? "" : `<span class="rt-cell__w">${escapeHtml(weight)}%</span>`;
  return `<td><span class="rt-cell${blank ? " is-empty" : ""}"><span class="rt-cell__v">${showNum(score)}</span>${w}</span></td>`;
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

// при старте подставляем последний введённый номер (если есть) и фокусируемся
try {
  const last = localStorage.getItem(LAST_ZACH_KEY);
  if (last) zachInput.value = last;
} catch (_) { /* приватный режим */ }
zachInput.focus();
zachInput.select();
