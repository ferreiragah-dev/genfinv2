/** Accessible native primitives shared by all routes. */
import { openModal, preference, toast } from "./utils.js";

export function initComponents() {
  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open]");
    if (opener) openModal(opener.dataset.open);
    const closer = event.target.closest("[data-close]");
    if (closer) closer.closest("dialog")?.close();
    const message = event.target.closest("[data-toast]");
    if (message) toast(message.dataset.toast);
    const favorite = event.target.closest("[data-toggle-favorite]");
    if (favorite) {
      const active = favorite.getAttribute("aria-pressed") !== "true";
      favorite.setAttribute("aria-pressed", String(active));
      favorite.querySelector("i").className =
        `${active ? "fa-solid" : "fa-regular"} fa-star`;
    }
    document.querySelectorAll("details.dropdown[open]").forEach((dropdown) => {
      if (!dropdown.contains(event.target)) dropdown.open = false;
    });
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      if (
        event.target === dialog &&
        (event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom)
      )
        dialog.close();
    });
  });
  initSearch();
  initPrivacy();
  document
    .getElementById("design-form")
    ?.addEventListener("submit", (event) => {
      event.preventDefault();
      toast("Formulário válido. Este exemplo não salva dados.");
    });
  document
    .querySelectorAll("#server-messages span")
    .forEach((message) => toast(message.textContent));
  try {
    const flash = sessionStorage.getItem("genfin:flash");
    if (flash) {
      toast(flash);
      sessionStorage.removeItem("genfin:flash");
    }
  } catch {
    /* Device preferences are optional. */
  }
}

function initSearch() {
  const search = document.getElementById("global-search");
  if (!search) return;
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openModal("search-modal");
      search.focus();
    }
  });
  const normalize = (text) =>
    text
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  search.addEventListener("input", () => {
    document.querySelectorAll("[data-search-label]").forEach((link) => {
      link.hidden = !normalize(link.dataset.searchLabel).includes(
        normalize(search.value.trim()),
      );
    });
    const transactions = document.getElementById("search-transactions");
    transactions.href = `/transactions/?q=${encodeURIComponent(search.value.trim())}`;
    transactions.querySelector("span").textContent = search.value
      ? `Buscar “${search.value}” nas transações`
      : "Buscar nas transações";
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      document.querySelector(".search-result:not([hidden])")?.click();
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      document.querySelector(".search-result:not([hidden])")?.focus();
    }
  });
}

function initPrivacy() {
  let privateMode = Boolean(preference("privacy"));
  const toggle = document.getElementById("privacy-toggle");
  const setting = document.getElementById("privacy-setting");
  function apply() {
    document.documentElement.classList.toggle("privacy-on", privateMode);
    toggle?.setAttribute("aria-pressed", String(privateMode));
    toggle?.setAttribute(
      "aria-label",
      privateMode ? "Mostrar valores" : "Ocultar valores",
    );
    if (toggle) {
      toggle.title = privateMode ? "Mostrar valores" : "Ocultar valores";
      toggle.querySelector("i").className =
        `fa-regular ${privateMode ? "fa-eye-slash" : "fa-eye"}`;
    }
    if (setting) setting.checked = privateMode;
  }
  apply();
  toggle?.addEventListener("click", () => {
    privateMode = !privateMode;
    preference("privacy", privateMode);
    apply();
  });
  setting?.addEventListener("change", () => {
    privateMode = setting.checked;
    preference("privacy", privateMode);
    apply();
    toast("Preferência salva neste navegador.");
  });
}
