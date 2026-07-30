/**
 * Мелкие помощники без состояния: выборка узлов, экранирование, форматирование.
 * Ни от чего не зависит, кроме констант.
 */

import { DASH } from "./config.js";

/** Короткая выборка одного узла. */
export const $ = (sel, root = document) => root.querySelector(sel);

/** Экранирование перед вставкой в innerHTML. */
export function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

/** Русское склонение по числу: plural(3, ["пара", "пары", "пар"]) → "пары". */
export function plural(n, forms) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}

export const disciplines = (n) => `${n} ${plural(n, ["дисциплина", "дисциплины", "дисциплин"])}`;

/** Бек присылает пропуски и как null, и как "-", и как пустую строку. */
export function isBlank(v) {
  return v === null || v === undefined || v === "-" || v === "";
}

export function isZeroWeight(v) {
  return v === 0 || v === "0" || v === 0.0;
}

/** Значение для ячейки таблицы: прочерк вместо пустоты, остальное экранируем. */
export function showNum(v) {
  return isBlank(v) ? DASH : escapeHtml(v);
}

/** Класс раскраски оценки — цвета заданы в css/rating.css. */
export function gradeClass(grade) {
  switch (String(grade).trim()) {
    case "Отл":
    case "Зачтено":
      return "is-good";
    case "Хор":
      return "is-ok";
    case "Удовл":
      return "is-mid";
    case "Неуд":
    case "Не зачтено":
      return "is-bad";
    default:
      return "is-none";
  }
}

/** Рейтинговая запись отличается от оценочной наличием контрольных точек. */
export function isRatingRecord(rec) {
  return rec && Array.isArray(rec.control_points);
}

/** Печать ВГУИТ — иллюстрация для экранов состояний. */
export const sealSvg =
  '<svg class="state__seal" viewBox="0 0 200 200" aria-hidden="true"><use href="#seal-mini"/></svg>';
