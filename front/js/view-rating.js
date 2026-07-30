/**
 * Экран рейтинга: загрузка ведомостей и их отрисовка.
 *
 * Каждый вид ведомости — отдельный запрос; часть может не ответить, поэтому
 * идём через allSettled и показываем то, что пришло, с баннером о недогрузе.
 * Детализацию контрольной точки открывает js/kt-popup.js по клику на ячейку.
 */

import { DASH, VED_TYPES } from "./config.js";
import { apiGet } from "./api.js";
import {
  $,
  disciplines,
  escapeHtml,
  gradeClass,
  isBlank,
  isRatingRecord,
  sealSvg,
  showNum,
} from "./utils.js";

const ratingContent = $("#rating-content");

/** Очистка при выходе из зачётки. */
export function clearRating() {
  ratingContent.innerHTML = "";
}

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

export async function loadRating(zach) {
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
