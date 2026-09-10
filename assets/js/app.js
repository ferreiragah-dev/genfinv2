import { initComponents } from "./components.js";
import { initSidebar } from "./sidebar.js";
import { initNotifications } from "./notifications.js";
import { initRecords } from "./records.js";

function init() {
  initComponents();
  initSidebar();
  initNotifications();
  initRecords();
}
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
