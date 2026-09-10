/** CRUD orchestration shared by transaction and planning forms. */
import {
  api,
  fillForm,
  localDate,
  openModal,
  reloadWithMessage,
  resetFormErrors,
  readJSON,
  showFormErrors,
  toast,
} from "./utils.js";

const recordTypes = {
  transaction: {
    form: "transaction-form",
    modal: "transaction-modal",
    title: "transaction-modal-title",
    endpoint: "/api/transactions/",
    createTitle: "Nova transação",
  },
  portfolio: {
    form: "portfolio-form",
    modal: "portfolio-modal",
    title: "portfolio-modal-title",
    endpoint: "/api/portfolio/",
  },
};

export function initRecords() {
  const vehicleCategories = readJSON("vehicle-categories", []);
  const syncVehicle = (form) => {
    const field = document.getElementById("tx-vehicle-field");
    if (!field || !form.elements.vehicle) return;
    const needed = vehicleCategories.includes(form.elements.category.value);
    field.hidden = !needed;
    form.elements.vehicle.required = needed;
    form.elements.vehicle.disabled = !needed;
    if (!needed) form.elements.vehicle.value = "";
  };
  for (const [type, config] of Object.entries(recordTypes)) {
    const form = document.getElementById(config.form);
    if (!form) continue;
    if (type === "transaction") {
      form.elements.category.addEventListener("change", () =>
        syncVehicle(form),
      );
      syncVehicle(form);
    }
    document.querySelectorAll(`[data-new-${type}]`).forEach((button) =>
      button.addEventListener("click", () => {
        form.reset();
        resetFormErrors(form);
        form.action = config.endpoint;
        const title = document.getElementById(config.title);
        title.textContent = config.createTitle || title.dataset.createTitle;
        if (type === "transaction") {
          form.elements.date.value = localDate();
          form.elements.category.value = button.dataset.category || "Outros";
          form.elements.vehicle.value = button.dataset.vehicle || "";
          if (button.dataset.description) {
            form.elements.description.value = button.dataset.description.slice(
              0,
              120,
            );
          }
          syncVehicle(form);
        }
        openModal(config.modal);
      }),
    );
    document.querySelectorAll(`[data-edit-${type}]`).forEach((button) =>
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const id = button.getAttribute(`data-edit-${type}`);
          const data = await api(`${config.endpoint}${id}/`);
          form.reset();
          resetFormErrors(form);
          fillForm(form, data);
          if (type === "transaction") syncVehicle(form);
          form.action = `${config.endpoint}${id}/save/`;
          document.getElementById(config.title).textContent =
            type === "transaction" ? "Editar transação" : "Editar registro";
          openModal(config.modal);
        } catch (error) {
          toast(error.message, "error");
        } finally {
          button.disabled = false;
        }
      }),
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("[type=submit]");
      if (button.disabled) return;
      button.disabled = true;
      button.classList.add("loading");
      form.setAttribute("aria-busy", "true");
      resetFormErrors(form);
      try {
        const result = await api(form.action, {
          method: "POST",
          body: new FormData(form),
        });
        reloadWithMessage(result.message);
      } catch (error) {
        showFormErrors(form, error);
      } finally {
        button.disabled = false;
        button.classList.remove("loading");
        form.removeAttribute("aria-busy");
      }
    });
  }
  initDelete();
}

function initDelete() {
  let endpoint = "";
  document.querySelectorAll("[data-delete]").forEach((button) =>
    button.addEventListener("click", () => {
      endpoint = button.dataset.delete;
      document.getElementById("confirm-description").textContent =
        button.dataset.name;
      openModal("confirm-modal");
    }),
  );
  document
    .getElementById("confirm-delete")
    ?.addEventListener("click", async (event) => {
      if (!endpoint) return;
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const result = await api(endpoint, { method: "POST" });
        reloadWithMessage(result.message);
      } catch (error) {
        toast(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
}
