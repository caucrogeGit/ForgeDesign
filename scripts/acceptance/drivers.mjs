// Pilotes sans dépendance (WebSocket global de Node 24) : Chromium (CDP) et Firefox
// (WebDriver BiDi), même interface. Chaque page reçoit, avant ses propres scripts,
// un écouteur des violations CSP ; toutes les requêtes sont relevées (réseau local).
const CSP_BODY = `window.__cspViolations = []; document.addEventListener("securitypolicyviolation", (e) => window.__cspViolations.push(e.violatedDirective + " " + (e.blockedURI || "")));`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class Socket {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.listeners = [];
    this.ready = new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
    this.ws.onmessage = (message) => {
      const data = JSON.parse(message.data);
      if (data.id !== undefined && this.pending.has(data.id)) {
        const { resolve, reject } = this.pending.get(data.id);
        this.pending.delete(data.id);
        if (data.error) reject(new Error(`${data.error.message ?? data.error} ${data.message ?? ""}`));
        else resolve(data.result);
      } else {
        for (const listener of this.listeners) listener(data);
      }
    };
  }
  send(method, params = {}, extra = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, ...extra }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  close() {
    this.ws.close();
  }
}

const KEYS = {
  ArrowLeft: { code: 37, bidi: "\uE012" },
  ArrowUp: { code: 38, bidi: "\uE013" },
  ArrowRight: { code: 39, bidi: "\uE014" },
  ArrowDown: { code: 40, bidi: "\uE015" },
  Escape: { code: 27, bidi: "\uE00C" },
  Enter: { code: 13, bidi: "\uE007" },
  Tab: { code: 9, bidi: "\uE004" },
  Backspace: { code: 8, bidi: "\uE003" },
  F2: { code: 113, bidi: "\uE032" },
};

async function waitFor(check, what, timeout = 8000) {
  const start = Date.now();
  for (;;) {
    const value = await check();
    if (value) return value;
    if (Date.now() - start > timeout) throw new Error(`délai dépassé : ${what}`);
    await sleep(50);
  }
}

export async function chromium(port) {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  const socket = new Socket(target.webSocketDebuggerUrl);
  await socket.ready;
  const posts = [];
  const requests = [];
  const errors = [];
  const networkErrors = [];
  let loads = 0;
  socket.listeners.push((event) => {
    if (event.method === "Network.requestWillBeSent") {
      requests.push(event.params.request.url);
      if (event.params.request.method === "POST") posts.push(event.params.request.url);
    }
    if (event.method === "Page.loadEventFired") loads += 1;
    if (event.method === "Runtime.exceptionThrown") errors.push(event.params.exceptionDetails.text + " " + (event.params.exceptionDetails.exception?.description ?? ""));
    if (event.method === "Log.entryAdded" && event.params.entry.level === "error") {
      (event.params.entry.source === "network" ? networkErrors : errors).push(`log: ${event.params.entry.text}`);
    }
    if (event.method === "Runtime.consoleAPICalled" && event.params.type === "error") errors.push(`console: ${JSON.stringify(event.params.args)}`);
    if (event.method === "Page.javascriptDialogOpening") errors.push(`dialog: ${event.params.message}`);
  });
  for (const domain of ["Page", "Runtime", "Network", "Log"]) await socket.send(`${domain}.enable`);
  await socket.send("Page.addScriptToEvaluateOnNewDocument", { source: `(() => { ${CSP_BODY} })();` });
  await socket.send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  let buttons = 0;
  const mouse = (type, x, y) =>
    socket.send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons, clickCount: 1, pointerType: "mouse" });
  return {
    name: "chromium",
    posts,
    requests,
    errors,
    networkErrors,
    async goto(url) {
      const before = loads;
      await socket.send("Page.navigate", { url });
      await waitFor(() => loads > before, `chargement ${url}`);
    },
    async eval(expression) {
      const result = await socket.send("Runtime.evaluate", {
        expression: `(async () => JSON.stringify(await (async () => (${expression}))()))()`,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) throw new Error(`eval : ${result.exceptionDetails.exception?.description ?? result.exceptionDetails.text}`);
      return result.result.value === undefined ? undefined : JSON.parse(result.result.value);
    },
    async down(x, y) {
      await mouse("mouseMoved", x, y);
      buttons = 1;
      await mouse("mousePressed", x, y);
    },
    async move(x, y) {
      await mouse("mouseMoved", x, y);
    },
    async up(x, y) {
      buttons = 0;
      await mouse("mouseReleased", x, y);
    },
    async key(key, { alt = false, ctrl = false, shift = false } = {}) {
      const { code } = KEYS[key];
      const modifiers = (alt ? 1 : 0) | (ctrl ? 2 : 0) | (shift ? 8 : 0);
      const held = [
        ...(ctrl ? [["Control", "ControlLeft", 17]] : []),
        ...(shift ? [["Shift", "ShiftLeft", 16]] : []),
        ...(alt ? [["Alt", "AltLeft", 18]] : []),
      ];
      for (const [name, physical, vk] of held) await socket.send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: name, code: physical, windowsVirtualKeyCode: vk, modifiers });
      await socket.send("Input.dispatchKeyEvent", { type: "rawKeyDown", key, code: key, windowsVirtualKeyCode: code, modifiers });
      await socket.send("Input.dispatchKeyEvent", { type: "keyUp", key, code: key, windowsVirtualKeyCode: code, modifiers });
      for (const [name, physical, vk] of held.reverse()) await socket.send("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: physical, windowsVirtualKeyCode: vk });
    },
    loads: () => loads,
    // Entrée réelle : keyDown portant le texte \r (keypress, activation native).
    async enter() {
      await socket.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
      await socket.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
    },
    // Saisie réelle : insertion de texte à la sélection courante (événements input).
    async type(text) {
      await socket.send("Input.insertText", { text });
    },
    async setJavaScript(enabled) {
      await socket.send("Emulation.setScriptExecutionDisabled", { value: !enabled });
    },
    close: () => socket.close(),
  };
}

function bidiValue(remote) {
  return remote.type === "string" ? remote.value : undefined;
}

export async function firefox(port) {
  const socket = new Socket(`ws://127.0.0.1:${port}/session`);
  await socket.ready;
  await socket.send("session.new", { capabilities: { alwaysMatch: { acceptInsecureCerts: true, unhandledPromptBehavior: { default: "ignore" } } } });
  const tree = await socket.send("browsingContext.getTree", {});
  const context = tree.contexts[0].context;
  await socket.send("browsingContext.setViewport", { context, viewport: { width: 1280, height: 900 } });
  // Fenêtre headless au premier plan : sans cela, Firefox n'émet aucun événement focus.
  await socket.send("browsingContext.activate", { context });
  const posts = [];
  const requests = [];
  const errors = [];
  let loads = 0;
  socket.listeners.push((event) => {
    if (event.method === "network.beforeRequestSent") {
      requests.push(event.params.request.url);
      if (event.params.request.method === "POST") posts.push(event.params.request.url);
    }
    if (event.method === "browsingContext.load" && event.params.context === context) loads += 1;
    if (event.method === "log.entryAdded" && event.params.level === "error") errors.push(`log: ${event.params.text}`);
    if (event.method === "browsingContext.userPromptOpened") errors.push(`dialog: ${event.params.message}`);
  });
  await socket.send("script.addPreloadScript", { functionDeclaration: `() => { ${CSP_BODY} }` });
  await socket.send("session.subscribe", {
    events: ["network.beforeRequestSent", "browsingContext.load", "log.entryAdded", "browsingContext.userPromptOpened"],
  });
  const pointer = (actions) =>
    socket.send("input.performActions", {
      context,
      actions: [{ type: "pointer", id: "mouse", parameters: { pointerType: "mouse" }, actions }],
    });
  const at = (x, y) => ({ type: "pointerMove", x: Math.round(x), y: Math.round(y), origin: "viewport", duration: 0 });
  return {
    name: "firefox",
    posts,
    requests,
    errors,
    async goto(url) {
      await socket.send("browsingContext.navigate", { context, url, wait: "complete" });
    },
    async eval(expression) {
      const result = await socket.send("script.evaluate", {
        expression: `(async () => JSON.stringify(await (async () => (${expression}))()))()`,
        target: { context },
        awaitPromise: true,
        resultOwnership: "none",
      });
      if (result.type === "exception") throw new Error(`eval : ${result.exceptionDetails.text}`);
      const text = bidiValue(result.result);
      return text === undefined ? undefined : JSON.parse(text);
    },
    async down(x, y) {
      await pointer([at(x, y), { type: "pointerDown", button: 0 }]);
    },
    async move(x, y) {
      await pointer([at(x, y)]);
    },
    async up(x, y) {
      await pointer([at(x, y), { type: "pointerUp", button: 0 }]);
    },
    async key(key, { alt = false, ctrl = false, shift = false } = {}) {
      const value = KEYS[key].bidi;
      const held = [...(ctrl ? ["\uE009"] : []), ...(shift ? ["\uE008"] : []), ...(alt ? ["\uE00A"] : [])];
      const actions = [
        ...held.map((modifier) => ({ type: "keyDown", value: modifier })),
        { type: "keyDown", value },
        { type: "keyUp", value },
        ...held.reverse().map((modifier) => ({ type: "keyUp", value: modifier })),
      ];
      await socket.send("input.performActions", { context, actions: [{ type: "key", id: "keyboard", actions }] });
      await socket.send("input.releaseActions", { context });
    },
    loads: () => loads,
    async rawKeys(actions) {
      await socket.send("input.performActions", { context, actions: [{ type: "key", id: "keyboard", actions }] });
      await socket.send("input.releaseActions", { context });
    },
    // Entrée réelle : touche Retour (\uE006), et non Entrée du pavé numérique.
    async enter() {
      await socket.send("input.performActions", { context, actions: [{ type: "key", id: "keyboard", actions: [{ type: "keyDown", value: "\uE006" }, { type: "keyUp", value: "\uE006" }] }] });
      await socket.send("input.releaseActions", { context });
    },
    async type(text) {
      const actions = [...text].flatMap((value) => [{ type: "keyDown", value }, { type: "keyUp", value }]);
      await socket.send("input.performActions", { context, actions: [{ type: "key", id: "keyboard", actions }] });
      await socket.send("input.releaseActions", { context });
    },
    close: async () => {
      try {
        await socket.send("session.end", {});
      } catch {}
      socket.close();
    },
  };
}

export { sleep, waitFor };
