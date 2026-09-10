/** Chart.js adapter. Charts receive computed data, never business rules. */
import { money } from "./utils.js";

export function initCharts(data) {
  if (!window.Chart) {
    document
      .querySelectorAll(".chart-container,.donut-container")
      .forEach((container) => {
        const message = document.createElement("p");
        message.className = "chart-fallback";
        message.textContent =
          "Não foi possível carregar o gráfico. Os totais continuam disponíveis nos cartões.";
        container.replaceChildren(message);
      });
    return;
  }
  const Chart = window.Chart;
  Chart.defaults.color = "#64748b";
  Chart.defaults.font.family = "Inter, sans-serif";
  Chart.defaults.font.size = 10;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = matchMedia("(prefers-reduced-motion: reduce)")
    .matches
    ? false
    : { duration: 600 };
  const cashflow = document.getElementById("cashflow-chart");
  let chart;
  if (cashflow) {
    const context = cashflow.getContext("2d");
    const gradient = context.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, "rgba(79,124,255,.22)");
    gradient.addColorStop(1, "rgba(79,124,255,0)");
    chart = new Chart(cashflow, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Receitas",
            data: data.income,
            borderColor: "#4F7CFF",
            backgroundColor: gradient,
            fill: true,
            borderWidth: 2,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: "Despesas",
            data: data.expense,
            borderColor: "#A78BFA",
            backgroundColor: "transparent",
            borderWidth: 2,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        layout: { padding: { top: 5, right: 5 } },
        plugins: {
          tooltip: {
            backgroundColor: "#152039",
            borderColor: "#24334b",
            borderWidth: 1,
            padding: 12,
            displayColors: true,
            callbacks: {
              title: (items) => `Dia ${items[0].label}`,
              label: (item) => `${item.dataset.label}: ${money(item.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { maxTicksLimit: 7, maxRotation: 0, padding: 10 },
          },
          y: {
            beginAtZero: true,
            border: { display: false },
            grid: { color: "rgba(148,163,184,.07)", drawTicks: false },
            ticks: {
              maxTicksLimit: 5,
              padding: 10,
              callback: (value) =>
                value >= 1000 ? `${value / 1000} mil` : value,
            },
          },
        },
      },
    });
  }
  const categories = document.getElementById("categories-chart");
  if (categories && data.categories?.length)
    new Chart(categories, {
      type: "doughnut",
      data: {
        labels: data.categories.map((item) => item.label),
        datasets: [
          {
            data: data.categories.map((item) => item.value),
            backgroundColor: data.categories.map((item) => item.color),
            borderColor: "#0B1224",
            borderWidth: 4,
            borderRadius: 3,
            hoverOffset: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "78%",
        plugins: {
          tooltip: {
            backgroundColor: "#152039",
            callbacks: {
              label: (item) => `${item.label}: ${money(item.parsed)}`,
            },
          },
        },
      },
    });
  const tabs = [...document.querySelectorAll("[data-chart-mode]")];
  function activate(tab) {
    tabs.forEach((button) => {
      button.setAttribute("aria-selected", String(button === tab));
      button.tabIndex = button === tab ? 0 : -1;
    });
    document
      .getElementById("cashflow-panel")
      ?.setAttribute("aria-labelledby", tab.id);
    if (!chart) return;
    const daily = tab.dataset.chartMode === "daily";
    chart.data.datasets[0].data = daily ? data.dailyIncome : data.income;
    chart.data.datasets[1].data = daily ? data.dailyExpense : data.expense;
    chart.update();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next =
          event.key === "Home"
            ? tabs[0]
            : event.key === "End"
              ? tabs.at(-1)
              : tabs[
                  (index +
                    (event.key === "ArrowRight" ? 1 : -1) +
                    tabs.length) %
                    tabs.length
                ];
        activate(next);
        next.focus();
      }
    });
  });
}
