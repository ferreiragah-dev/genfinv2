import { api, toast } from "./utils.js";

export function initNotifications() {
  const toggle = document.getElementById("notifications-toggle");
  const panel = document.getElementById("notifications-panel");
  if (!toggle || !panel) return;
  function close() {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  }
  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".notification-wrap")) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      close();
      toggle.focus();
    }
  });
  document
    .getElementById("notifications-read")
    ?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await api("/api/preferences/", {
          method: "POST",
          json: { notifications_read: true },
        });
        toggle.querySelector(".notification-dot")?.remove();
        toast("Notificações marcadas como lidas.");
        close();
      } catch (error) {
        toast(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
}
