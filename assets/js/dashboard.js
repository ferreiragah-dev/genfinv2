import { api, readJSON, toast } from "./utils.js";
import { initCharts } from "./charts.js";

const widgets = {
  cashflow: "Fluxo de caixa",
  categories: "Categorias de gastos",
  heatmap: "Ritmo financeiro",
  recent: "Últimas movimentações",
  rankings: "Top gastos e receitas",
  score: "Saúde financeira",
  goals: "Reservas e metas",
  alerts: "Alertas",
  timeline: "Linha do tempo",
};

function initDashboard() {
  initCharts(readJSON("chart-data"));
  const settings = readJSON("widget-preferences");
  const options = document.getElementById("widget-options");
  if (!options) return;
  for (const [key, title] of Object.entries(widgets)) {
    const label = document.createElement("label");
    label.className = "widget-option";
    const text = document.createElement("span");
    text.textContent = title;
    const toggle = document.createElement("span");
    toggle.className = "toggle";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = key;
    checkbox.checked = settings[key] !== false;
    toggle.append(checkbox);
    label.append(text, toggle);
    options.append(label);
  }
  document.getElementById("widgets-reset").addEventListener("click", () =>
    options.querySelectorAll("input").forEach((input) => {
      input.checked = true;
    }),
  );
  document
    .getElementById("widgets-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("[type=submit]");
      button.disabled = true;
      const next = Object.fromEntries(
        [...options.querySelectorAll("input")].map((input) => [
          input.name,
          input.checked,
        ]),
      );
      try {
        await api("/api/preferences/", {
          method: "POST",
          json: { widgets: next },
        });
        document.querySelectorAll("[data-widget]").forEach((widget) => {
          widget.hidden = !next[widget.dataset.widget];
        });
        document.getElementById("widgets-drawer").close();
        window.dispatchEvent(new Event("resize"));
        toast("Sua visão geral está do seu jeito.");
      } catch (error) {
        toast(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
}
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", initDashboard, { once: true });
else initDashboard();
