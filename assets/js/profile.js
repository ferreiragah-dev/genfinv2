import { openModal } from "./utils.js";

const dialog = document.getElementById("reset-account-modal");
const form = document.getElementById("reset-account-form");

if (dialog && form) {
  const password = form.elements.namedItem("password");
  const submit = form.querySelector('[type="submit"]');
  const label = submit.textContent;
  let submitting = false;

  function clearPassword() {
    password.value = "";
  }
  function restoreForm() {
    clearPassword();
    submitting = false;
    submit.disabled = false;
    submit.textContent = label;
    form.removeAttribute("aria-busy");
  }

  dialog.addEventListener("close", clearPassword);
  window.addEventListener("pagehide", clearPassword);
  window.addEventListener("pageshow", restoreForm);
  form.addEventListener("submit", (event) => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    submitting = true;
    submit.disabled = true;
    submit.textContent = "Resetando conta…";
    form.setAttribute("aria-busy", "true");
  });
  if (dialog.hasAttribute("data-show-reset")) openModal(dialog.id);
}
