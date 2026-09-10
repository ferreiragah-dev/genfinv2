/** Shared formatting, HTTP and UI helpers. Never interpolate user data into HTML. */
export const money = (value) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    value,
  );
export const localDate = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

export function readJSON(id, fallback = {}) {
  try {
    return JSON.parse(
      document.getElementById(id)?.textContent || JSON.stringify(fallback),
    );
  } catch {
    return fallback;
  }
}

export function preference(key, value) {
  try {
    if (value !== undefined)
      localStorage.setItem(`genfin:${key}`, JSON.stringify(value));
    return JSON.parse(localStorage.getItem(`genfin:${key}`) || "null");
  } catch {
    return value ?? null;
  }
}

export async function api(url, { method = "GET", body, json } = {}) {
  const headers = {
    Accept: "application/json",
    "X-Requested-With": "XMLHttpRequest",
  };
  if (method !== "GET") {
    headers["X-CSRFToken"] =
      document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {
      method,
      body,
      headers,
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (response.redirected || response.status === 401)
      throw new Error("Sua sessão expirou. Entre novamente para continuar.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(
        data.message ||
          (response.status === 403
            ? "Não foi possível validar a sessão. Atualize a página."
            : "Não foi possível salvar. Confira os dados e tente novamente."),
      );
      error.fields = data.errors;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "A conexão demorou mais que o esperado. Confira se o registro foi salvo antes de tentar novamente.",
      );
    if (error instanceof TypeError)
      throw new Error(
        "Sem conexão com o servidor. Verifique sua conexão e tente novamente.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function toast(message, type = "success") {
  const container = document.getElementById("toasts");
  if (!container) return;
  const item = document.createElement("div");
  item.className = `toast ${type === "error" ? "error" : ""}`;
  const icon = document.createElement("i");
  icon.className = `fa-solid ${type === "error" ? "fa-circle-exclamation" : "fa-circle-check"}`;
  icon.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.textContent = message;
  const close = document.createElement("button");
  close.className = "icon-button";
  close.setAttribute("aria-label", "Dispensar mensagem");
  close.textContent = "×";
  close.addEventListener("click", () => item.remove());
  item.append(icon, text, close);
  container.append(item);
  setTimeout(() => item.remove(), 7000);
}

export function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal || modal.open) return;
  modal.showModal();
  document.body.style.overflow = "hidden";
  modal.addEventListener(
    "close",
    () => {
      document.body.style.overflow = "";
    },
    { once: true },
  );
}

export function showFormErrors(form, error) {
  const summary = form.querySelector(".error-summary");
  form
    .querySelectorAll("[aria-invalid]")
    .forEach((input) => input.removeAttribute("aria-invalid"));
  const errors = [];
  if (error.fields)
    Object.entries(error.fields).forEach(([name, values]) => {
      const field = form.elements.namedItem(name);
      field?.setAttribute("aria-invalid", "true");
      const label = field?.labels?.[0]?.textContent || name;
      errors.push(
        `${label}: ${values.map((value) => value.message).join(" ")}`,
      );
    });
  if (summary) {
    summary.textContent = errors.join(" ") || error.message;
    summary.hidden = false;
    summary.scrollIntoView({ block: "nearest" });
  } else toast(error.message, "error");
  form.querySelector("[aria-invalid=true]")?.focus();
}

export function fillForm(form, values) {
  for (const [name, value] of Object.entries(values)) {
    const field = form.elements.namedItem(name);
    if (field) field.value = value ?? "";
  }
}

export function resetFormErrors(form) {
  const summary = form.querySelector(".error-summary");
  if (summary) summary.hidden = true;
  form
    .querySelectorAll("[aria-invalid]")
    .forEach((input) => input.removeAttribute("aria-invalid"));
}

export function reloadWithMessage(message) {
  try {
    sessionStorage.setItem("genfin:flash", message);
  } catch {
    /* Storage may be disabled. */
  }
  location.reload();
}
