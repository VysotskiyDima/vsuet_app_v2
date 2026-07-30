/**
 * Попап детализации контрольной точки.
 *
 * Разметку создаёт сам — в index.html её нет. Открывается делегированным
 * кликом по ячейке .rt-total--clickable из таблицы рейтинга, поэтому модулю
 * достаточно один раз подписаться на document и не знать про view-rating.
 *
 * На мобилке ведёт себя как шторка: закрывается свайпом вниз. Скролл страницы
 * на время показа фиксируется через position:fixed — iOS игнорирует
 * overflow:hidden на body.
 */

import { DASH, WORK_LABELS } from "./config.js";
import { escapeHtml, isBlank, isZeroWeight, showNum } from "./utils.js";

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
