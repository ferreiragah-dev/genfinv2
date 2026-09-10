/** Responsive navigation, including keyboard closure and focus restoration. */
export function initSidebar() {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const overlay = document.getElementById("sidebar-overlay");
  if (!sidebar || !toggle) return;
  const narrow = matchMedia("(max-width: 800px)");
  let opened = false;
  function setOpen(value) {
    opened = value;
    sidebar.classList.toggle("is-open", value);
    overlay?.classList.toggle("is-open", value);
    toggle.setAttribute("aria-expanded", String(value));
    toggle.setAttribute(
      "aria-label",
      value ? "Fechar navegação" : "Abrir navegação",
    );
    sidebar.inert = narrow.matches && !value;
    document.body.style.overflow = value && narrow.matches ? "hidden" : "";
    if (value) sidebar.querySelector("a")?.focus();
  }
  setOpen(false);
  toggle.addEventListener("click", () => setOpen(!opened));
  overlay?.addEventListener("click", () => {
    setOpen(false);
    toggle.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (!opened || !narrow.matches) return;
    if (event.key === "Escape") {
      setOpen(false);
      toggle.focus();
    }
    if (event.key === "Tab") {
      const focusable = [...sidebar.querySelectorAll("a,button")];
      const first = focusable[0],
        last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  narrow.addEventListener("change", () => setOpen(false));
}
