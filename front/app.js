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
const viewRating    = $("#view-rating");
const loginForm     = $("#login-form");
const zachInput     = $("#zach");
const loginBtn      = $("#login-btn");
const loginError    = $("#login-error");
const demoFill      = $("#demo-fill");
const currentZach   = $("#current-zach");
const logoutBtn     = $("#logout-btn");
const ratingContent = $("#rating-content");

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
logoutBtn.addEventListener("click", closeRating);

// ============================================================
// Переключение экранов
// ============================================================
const LAST_ZACH_KEY = "rating:lastZach";
function rememberZach(zach) { try { localStorage.setItem(LAST_ZACH_KEY, zach); } catch (_) {} }

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