/**
 * Экран входа: ввод номера зачётки и его проверка на беке.
 *
 * Про сессию модуль ничего не знает — при успехе зовёт колбэк onSuccess,
 * который передаёт main.js. Иначе получилось бы кольцо login → session → login.
 */

import { $ } from "./utils.js";
import { apiGet } from "./api.js";

const loginForm = $("#login-form");
const zachInput = $("#zach");
const loginBtn = $("#login-btn");
const loginError = $("#login-error");
const demoFill = $("#demo-fill");

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

/** Возврат экрана в исходный вид — вызывается при выходе из зачётки. */
export function resetLoginForm() {
  setLoginError("");
  zachInput.value = "";
  zachInput.focus();
}

export function focusZachInput() {
  zachInput.focus();
}

export function initLogin({ onSuccess }) {
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
      if (data && data.exists) onSuccess(zach);
      else setLoginError(`Зачётная книжка № ${zach} не найдена. Проверьте номер.`);
    } catch (_) {
      setLoginError("Не удалось связаться с сервером. Проверьте соединение.");
    } finally {
      setLoginLoading(false);
    }
  });

  // В номере только цифры — чистим ввод на лету.
  zachInput.addEventListener("input", () => {
    const cleaned = zachInput.value.replace(/\D/g, "");
    if (cleaned !== zachInput.value) zachInput.value = cleaned;
    if (!loginError.hidden) setLoginError("");
  });

  if (demoFill) {
    demoFill.addEventListener("click", () => {
      zachInput.value = "247162";
      zachInput.focus();
    });
  }
}
