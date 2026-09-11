import { api, openModal, reloadWithMessage, toast } from "./utils.js";

const root = document.getElementById("open-finance");
const feedback = document.getElementById("connection-feedback");
let sdkPromise;
let widget;
let connecting = false;

function loadWidget() {
  if (window.PluggyConnect) return Promise.resolve();
  if (sdkPromise) return sdkPromise;
  sdkPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src =
      "https://cdn.pluggy.ai/pluggy-connect/v2.8.2/pluggy-connect.js";
    script.onload = () => {
      clearTimeout(timer);
      if (window.PluggyConnect) resolve();
      else fail();
    };
    function fail() {
      clearTimeout(timer);
      script.remove();
      sdkPromise = undefined;
      reject(new Error("Não foi possível abrir a Pluggy. Tente novamente."));
    }
    const timer = setTimeout(fail, 15000);
    script.onerror = fail;
    document.head.append(script);
  });
  return sdkPromise;
}

function releaseWidget() {
  connecting = false;
  root.querySelectorAll("[data-connect-bank]").forEach((button) => {
    button.disabled = false;
  });
}

async function connect(button) {
  if (connecting) return;
  connecting = true;
  root.querySelectorAll("[data-connect-bank]").forEach((element) => {
    element.disabled = true;
  });
  feedback.textContent = "Preparando conexão segura…";
  try {
    await loadWidget();
    const body = new FormData();
    if (button.dataset.connectBank)
      body.set("connection_id", button.dataset.connectBank);
    const options = await api(root.dataset.tokenUrl, { method: "POST", body });
    widget = new window.PluggyConnect({
      connectToken: options.accessToken,
      connectorIds: options.connectorIds,
      includeSandbox: options.includeSandbox,
      ...(options.updateItem ? { updateItem: options.updateItem } : {}),
      language: "pt",
      theme:
        document.documentElement.dataset.theme === "light" ? "light" : "dark",
      countries: ["BR"],
      products: ["ACCOUNTS", "TRANSACTIONS"],
      allowConnectInBackground: false,
      onSuccess: async ({ item }) => {
        try {
          const result = await api(root.dataset.registerUrl, {
            method: "POST",
            json: { itemId: item.id },
          });
          reloadWithMessage(result.message);
        } catch (error) {
          feedback.textContent = `${error.message} Reabra a conexão para tentar salvá-la novamente.`;
          toast(error.message, "error");
        } finally {
          releaseWidget();
        }
      },
      onError: () => {
        feedback.textContent =
          "A conexão não foi concluída. Tente novamente na Pluggy.";
        toast(feedback.textContent, "error");
        releaseWidget();
      },
      onClose: releaseWidget,
    });
    widget.init();
    feedback.textContent = "Conclua as etapas na janela da Pluggy.";
  } catch (error) {
    feedback.textContent = error.message;
    toast(error.message, "error");
    releaseWidget();
  }
}

async function action(button, url, reload = false) {
  button.disabled = true;
  try {
    const result = await api(url, { method: "POST" });
    if (reload) reloadWithMessage(result.message);
    else {
      feedback.textContent = result.message;
      toast(result.message);
      button.closest("[data-bank-id]").dataset.bankStatus = "QUEUED";
      beginPolling();
    }
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

let pollTimer;
let pollCount = 0;
function beginPolling() {
  clearTimeout(pollTimer);
  pollCount = 0;
  pollTimer = setTimeout(poll, 5000);
}
async function poll() {
  try {
    const data = await api(root.dataset.statusUrl);
    let pending = false;
    for (const connection of data.connections) {
      const card = root.querySelector(
        `[data-bank-id="${Number(connection.id)}"]`,
      );
      if (!card) continue;
      if (
        connection.status === "UPDATED" &&
        card.dataset.bankStatus !== "UPDATED"
      ) {
        reloadWithMessage(
          "Movimentações importadas. Seu dashboard já foi atualizado.",
        );
        return;
      }
      card.dataset.bankStatus = connection.status;
      card.querySelector("[data-sync-message]").textContent =
        connection.sync_message;
      pending ||= [
        "QUEUED",
        "SYNCING",
        "UPDATING",
        "LOGIN_IN_PROGRESS",
      ].includes(connection.status);
    }
    if (pending && ++pollCount < 24) pollTimer = setTimeout(poll, 5000);
    else if (pending)
      feedback.textContent =
        "A importação ainda não terminou. Volte em alguns minutos. Se continuar aguardando, peça ao administrador para verificar o serviço de sincronização.";
  } catch (error) {
    feedback.textContent = error.message;
  }
}

root
  ?.querySelectorAll("[data-connect-bank]")
  .forEach((button) => button.addEventListener("click", () => connect(button)));
root
  ?.querySelectorAll("[data-sync-bank]")
  .forEach((button) =>
    button.addEventListener("click", () =>
      action(button, button.dataset.syncBank),
    ),
  );
root?.querySelectorAll("[data-disconnect-bank]").forEach((button) =>
  button.addEventListener("click", () => {
    const dialog = document.getElementById("disconnect-bank-dialog");
    dialog.returnValue = "cancel";
    dialog.addEventListener(
      "close",
      () => {
        if (dialog.returnValue === "confirm")
          action(button, button.dataset.disconnectBank, true);
      },
      { once: true },
    );
    openModal(dialog.id);
  }),
);
if (
  root?.querySelector(
    '[data-bank-status="QUEUED"], [data-bank-status="SYNCING"], [data-bank-status="UPDATING"], [data-bank-status="LOGIN_IN_PROGRESS"]',
  )
)
  beginPolling();
