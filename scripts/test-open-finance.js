/** Exercise the actual frontend widget contract without credentials or a browser. */
import assert from "node:assert/strict";
import { test } from "node:test";

const button = {
  dataset: {},
  disabled: false,
  addEventListener: (_, fn) => {
    button.click = fn;
  },
};
const feedback = { textContent: "" };
const root = {
  dataset: {
    tokenUrl: "/api/open-finance/token/",
    registerUrl: "/api/open-finance/items/",
  },
  querySelectorAll: (selector) =>
    selector === "[data-connect-bank]" ? [button] : [],
  querySelector: () => null,
};
globalThis.document = {
  getElementById: (id) =>
    ({ "open-finance": root, "connection-feedback": feedback })[id] || null,
  documentElement: { dataset: { theme: "dark" } },
  querySelector: () => ({ value: "csrf-token" }),
};
let options;
let initialized = 0;
let reloads = 0;
globalThis.window = {
  PluggyConnect: class {
    constructor(value) {
      options = value;
    }
    init() {
      initialized++;
    }
  },
};
globalThis.location = {
  reload: () => {
    reloads++;
  },
};
const calls = [];
globalThis.fetch = async (url, request) => {
  calls.push({ url, request });
  return {
    ok: true,
    status: 200,
    json: async () =>
      url.endsWith("token/")
        ? {
            accessToken: "short-lived",
            connectorIds: [2],
            includeSandbox: true,
          }
        : { message: "Conexão salva." },
  };
};
await import("../assets/js/open-finance.js");

test("widget uses the Connect Token, sandbox allowlist and authenticated POST", async () => {
  await button.click();
  assert.equal(initialized, 1);
  assert.equal(options.connectToken, "short-lived");
  assert.equal(options.accessToken, undefined);
  assert.deepEqual(options.connectorIds, [2]);
  assert.equal(options.includeSandbox, true);
  assert.deepEqual(options.products, ["ACCOUNTS", "TRANSACTIONS"]);
  assert.equal(calls[0].request.method, "POST");
  assert.equal(calls[0].request.headers["X-CSRFToken"], "csrf-token");
  assert.equal(button.disabled, true);
  await options.onSuccess({
    item: {
      id: "item-id",
      clientUserId: "untrusted",
      credentials: "never-send",
    },
  });
  assert.equal(calls[1].url, "/api/open-finance/items/");
  assert.deepEqual(JSON.parse(calls[1].request.body), { itemId: "item-id" });
  assert.equal(reloads, 1);
  assert.equal(button.disabled, false);
});

test("network failure releases connect button and explains the failure", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("network down");
  };
  await button.click();
  assert.equal(button.disabled, false);
  assert.match(feedback.textContent, /Sem conexão com o servidor/);
  assert.equal(initialized, 1);
});
