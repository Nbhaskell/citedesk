// Screenshots and a walkthrough of the running app, taken with a headless Edge or Chrome driven
// over the DevTools protocol (no packages to install). The in-app browser pane is too narrow for a
// true 1280px capture, so this writes the files directly at the real width.
//
//   node scripts/capture.mjs <phase> <out dir>
//
// Phases: demo (every state, needs the demo database), few (Insights with too few decisions),
// empty (empty queue and Insights, needs an empty database), walkthrough (an animated PNG).
// Start the API on the matching database and the web dev server first (see docs/screenshots).
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32 } from "node:zlib";

const BROWSER =
  process.env.BROWSER_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const BASE = process.env.WEB_URL ?? "http://127.0.0.1:5174";
const PORT = 9333;
const [phase, outDir = "shots"] = process.argv.slice(2);
if (!["demo", "few", "empty", "walkthrough"].includes(phase ?? "")) {
  console.error("usage: node scripts/capture.mjs <demo|few|empty|walkthrough> <out dir>");
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// --- a minimal DevTools protocol client ----------------------------------------------------------
async function launch() {
  // A browser left over from an earlier run would answer on this port with its old storage and
  // settings, and the pictures would come out wrong without any error. Refuse instead.
  const taken = await fetch(`http://127.0.0.1:${PORT}/json/version`).then(
    () => true,
    () => false,
  );
  if (taken) throw new Error(`something is already listening on port ${PORT}; close that browser`);
  const profile = mkdtempSync(join(tmpdir(), "citedesk-capture-"));
  const proc = spawn(
    BROWSER,
    [
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      "--headless=new",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--hide-scrollbars",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  let target;
  for (let i = 0; i < 100 && !target; i += 1) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      target = list.find((t) => t.type === "page");
    } catch {
      /* not up yet */
    }
    if (!target) await sleep(200);
  }
  if (!target) throw new Error("the browser did not start");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });

  let seq = 0;
  const pending = new Map();
  const listeners = new Map();
  ws.addEventListener("message", (message) => {
    const data = JSON.parse(String(message.data));
    if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(new Error(`${data.error.message}`));
      else resolve(data.result);
    } else if (data.method) {
      for (const fn of listeners.get(data.method) ?? []) fn(data.params);
    }
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      seq += 1;
      pending.set(seq, { resolve, reject });
      ws.send(JSON.stringify({ id: seq, method, params }));
    });
  const on = (method, fn) => listeners.set(method, [...(listeners.get(method) ?? []), fn]);
  const close = async () => {
    ws.close();
    proc.kill();
    // The browser hands off to helper processes that are not its children, so end every process
    // that was started with this run's private profile folder.
    if (process.platform === "win32") {
      const script =
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like " +
        `'*${profile}*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`;
      const killer = spawn("powershell", ["-NoProfile", "-Command", script], { stdio: "ignore" });
      await new Promise((resolve) => killer.on("exit", resolve));
    }
  };
  return { send, on, close };
}

const browser = await launch();
const { send, on } = browser;
await send("Page.enable");
await send("Runtime.enable");

// --- the page: viewport, navigation, network, keys, pictures -------------------------------------
let viewport = { width: 1280, height: 800 };
async function setViewport(width, height) {
  viewport = { width, height };
  await send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 500,
  });
}

// Requests to the API can be let through, held (a loading state) or refused (an error state).
let network = "pass";
let held = [];
on("Fetch.requestPaused", ({ requestId }) => {
  if (network === "pass") void send("Fetch.continueRequest", { requestId }).catch(() => {});
  else if (network === "hold") held.push(requestId);
  else
    void send("Fetch.failRequest", { requestId, errorReason: "ConnectionRefused" }).catch(() => {});
});
// only the API: the dev server also serves source files under /src/api/, which must get through
await send("Fetch.enable", { patterns: [{ urlPattern: `${BASE}/api/*` }] });

async function evaluate(expression) {
  const { result, exceptionDetails } = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? "script failed");
  return result.value;
}

async function waitFor(expression, what, timeout = 10_000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await sleep(100);
  }
  throw new Error(`timed out waiting for ${what}`);
}

const ready = "document.querySelector('main h1') && !document.querySelector('[aria-busy=true]')";

/** Open a page and wait until it has stopped loading (unless `loading` is what is wanted). */
async function open(path, { mode = "pass", loading = false } = {}) {
  network = mode;
  held = [];
  await send("Page.navigate", { url: `${BASE}${path}` });
  await waitFor("document.readyState === 'complete' && document.querySelector('main h1')", "page");
  if (!loading && mode === "pass") await waitFor(ready, "content");
  await evaluate("document.fonts.ready.then(() => true)");
  await sleep(loading || mode !== "pass" ? 600 : 350);
}

/** Go from a page to another inside the app, without a reload, so router state is kept. */
async function clickText(selector, text) {
  const done = await evaluate(
    `(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
      .find((e) => e.textContent.trim().startsWith(${JSON.stringify(text)}));
      if (!el) return false; el.click(); return true; })()`,
  );
  if (!done) throw new Error(`nothing to click: ${selector} "${text}"`);
}

const KEYS = {
  Escape: { code: "Escape", vk: 27 },
  Enter: { code: "Enter", vk: 13, text: "\r" },
};
async function press(key, { shift = false } = {}) {
  const known = KEYS[key];
  const single = key.length === 1;
  const params = {
    key,
    code: known?.code ?? (key === "?" ? "Slash" : `Key${key.toUpperCase()}`),
    windowsVirtualKeyCode: known?.vk ?? (key === "?" ? 191 : key.toUpperCase().charCodeAt(0)),
    modifiers: shift ? 8 : 0,
    ...(single || known?.text ? { text: known?.text ?? key } : {}),
  };
  await send("Input.dispatchKeyEvent", { type: params.text ? "keyDown" : "rawKeyDown", ...params });
  await send("Input.dispatchKeyEvent", { type: "keyUp", ...params });
  await sleep(150);
}

async function typeInto(selector, text) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
  await send("Input.insertText", { text });
  await sleep(200);
}

const written = [];
/** A picture of the whole page at its real height (the viewport grows to fit, so the sticky
 *  footer lands at the bottom), written as WebP. */
async function shot(name, { full = true } = {}) {
  const { width } = viewport;
  const before = viewport.height;
  if (full) {
    const height = await evaluate(
      "Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)",
    );
    await setViewport(width, Math.min(Math.max(height, before), 6000));
    await sleep(250);
  }
  const { data } = await send("Page.captureScreenshot", { format: "webp", quality: 85 });
  const file = join(outDir, `${name}-${width}.webp`);
  writeFileSync(file, Buffer.from(data, "base64"));
  written.push(file);
  if (full) await setViewport(width, before);
}

async function frame() {
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  return Buffer.from(data, "base64");
}

// --- the states ----------------------------------------------------------------------------------
async function demoStates(name) {
  // the queue
  await open("/");
  await shot("queue-list");
  await open("/?show=all");
  await shot("queue-all");
  await open("/");
  await typeInto("#queue-search", "zzzz");
  await waitFor(
    "document.body.textContent.includes('No inquiries match this filter.')",
    "no results",
  );
  await shot("queue-no-results");
  await open("/", { mode: "hold", loading: true });
  await shot("queue-loading");
  await open("/", { mode: "fail" });
  await waitFor('document.body.textContent.includes("Can\'t reach Citedesk")', "error");
  await shot("queue-error");

  // the inquiry screen: waiting for review, opened from the queue so it has a list
  await open("/");
  await clickText("a[data-row]", "");
  await waitFor("document.querySelector('textarea')", "the draft");
  await sleep(300);
  await shot("detail-review");
  await press("a");
  await waitFor("document.body.textContent.includes('Saved in')", "the undo bar");
  await shot("detail-undo");
  await press("Escape");
  await sleep(200);
  await press("r");
  await waitFor(
    "document.activeElement && document.activeElement.tagName === 'TEXTAREA' && document.activeElement.id !== ''",
    "form",
  );
  await shot("detail-reject-form");

  // the other variants, by their ids in the demo database
  const variants = [
    ["detail-blocked", 2],
    ["detail-refusal", 3],
    ["detail-processing", 4],
    ["detail-rejected", 5],
    ["detail-approved", 6],
    ["detail-failed", 7],
    ["detail-escalated", 8],
    ["detail-exported", 9],
    ["detail-resolved", 10],
  ];
  for (const [label, id] of variants) {
    await open(`/inquiries/${id}`);
    await shot(label);
  }
  await open("/inquiries/1", { mode: "hold", loading: true });
  await shot("detail-loading");
  await open("/inquiries/1", { mode: "fail" });
  await waitFor('document.body.textContent.includes("Can\'t reach Citedesk")', "error");
  await shot("detail-error");
  await open("/inquiries/9999");
  await shot("detail-not-found");

  // Insights and Settings
  await open("/insights");
  await shot("insights");
  await typeInto("#insights-minutes, input[inputmode=decimal]", "12");
  await shot("insights-estimate");
  await open("/insights", { mode: "hold", loading: true });
  await shot("insights-loading");
  await open("/insights", { mode: "fail" });
  await waitFor('document.body.textContent.includes("Can\'t reach Citedesk")', "error");
  await shot("insights-error");
  await open("/settings");
  await shot("settings");
  await clickText("button", "Check again");
  // the answer can arrive from a status poll a moment before the button says "Check again"
  await waitFor(
    "document.body.textContent.includes('Last checked') && [...document.querySelectorAll('button')].some((b) => b.textContent === 'Check again')",
    "the check",
  );
  await shot("settings-checked");
  await open("/settings", { mode: "hold", loading: true });
  await shot("settings-loading");
  await open("/settings", { mode: "fail" });
  await waitFor('document.body.textContent.includes("Can\'t reach Citedesk")', "error");
  await shot("settings-error");

  // the shortcut list
  await open("/");
  await press("?", { shift: true });
  await waitFor("document.querySelector('[role=dialog]')", "the shortcut list");
  await shot("shortcut-list", { full: false });
  console.log(`${name}: done`);
}

async function fewStates() {
  await open("/insights");
  await shot("insights-too-few");
}

async function emptyStates() {
  await open("/");
  await shot("queue-empty");
  await open("/insights");
  await shot("insights-empty");
}

// --- the walkthrough: an animated PNG, from frames of the real app ---------------------------------
function chunk(type, data) {
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const out = Buffer.alloc(8 + data.length + 4);
  out.writeUInt32BE(data.length, 0);
  body.copy(out, 4);
  out.writeUInt32BE(crc32(body) >>> 0, 8 + data.length);
  return out;
}

function chunksOf(png) {
  const found = [];
  for (let at = 8; at < png.length;) {
    const length = png.readUInt32BE(at);
    found.push({
      type: png.toString("ascii", at + 4, at + 8),
      data: png.subarray(at + 8, at + 8 + length),
    });
    at += 12 + length;
  }
  return found;
}

/** Join PNG frames (same size and format) into one animated PNG. `delays` are in milliseconds. */
function animatedPng(frames, delays) {
  const parts = [Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])];
  const first = chunksOf(frames[0]);
  const header = first.find((c) => c.type === "IHDR").data;
  const [width, height] = [header.readUInt32BE(0), header.readUInt32BE(4)];
  parts.push(chunk("IHDR", header));
  const control = Buffer.alloc(8);
  control.writeUInt32BE(frames.length, 0); // frames
  control.writeUInt32BE(0, 4); // loop forever
  parts.push(chunk("acTL", control));
  let sequence = 0;
  frames.forEach((png, index) => {
    const fc = Buffer.alloc(26);
    fc.writeUInt32BE(sequence++, 0);
    fc.writeUInt32BE(width, 4);
    fc.writeUInt32BE(height, 8);
    fc.writeUInt16BE(delays[index], 20); // delay numerator, in thousandths of a second
    fc.writeUInt16BE(1000, 22);
    parts.push(chunk("fcTL", fc));
    const image = Buffer.concat(
      chunksOf(png)
        .filter((c) => c.type === "IDAT")
        .map((c) => c.data),
    );
    if (index === 0) {
      parts.push(chunk("IDAT", image));
    } else {
      const sequenced = Buffer.alloc(4);
      sequenced.writeUInt32BE(sequence++, 0);
      parts.push(chunk("fdAT", Buffer.concat([sequenced, image])));
    }
  });
  parts.push(chunk("IEND", Buffer.alloc(0)));
  return Buffer.concat(parts);
}

async function walkthrough() {
  const frames = [];
  const delays = [];
  const add = async (ms) => {
    frames.push(await frame());
    delays.push(ms);
  };
  await evaluate("true");
  await open("/");
  await add(1800); // the queue
  await press("j");
  await add(900); // focus on the first row
  await press("Enter");
  await waitFor("document.querySelector('textarea')", "the draft");
  await sleep(300);
  await add(2400); // the draft, its checks and sources
  await press("a");
  await waitFor("document.body.textContent.includes('Saved in')", "the undo bar");
  // the bar is below the first screen of the draft: bring it into view for this frame
  await evaluate("document.querySelector('[class*=undo]')?.scrollIntoView({ block: 'center' })");
  await sleep(200);
  await add(1800); // the wait to undo
  await waitFor("document.body.textContent.includes('Copy reply')", "the approved reply", 12_000);
  await evaluate("window.scrollTo(0, 0)");
  await sleep(300);
  await add(2000); // approved, ready to copy
  // headless browsers have no clipboard; the app's own response to a copy is what is shown
  await evaluate(
    "Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => {} } })",
  );
  await clickText("button", "Copy reply");
  await waitFor("document.body.textContent.includes('Nothing was sent')", "the copy");
  await sleep(300);
  await add(2200); // copied
  await press("Escape");
  await sleep(600);
  await add(1400); // back in the queue
  await clickText("a", "Escalated");
  await waitFor("document.querySelector('a[data-row]')", "the escalated list");
  await sleep(300);
  await add(1500);
  await clickText("a[data-row]", "");
  await waitFor(
    "document.querySelector('main h1') && document.body.textContent.includes('Escalated')",
    "the escalated inquiry",
  );
  await sleep(400);
  await add(2600); // an escalated inquiry, markup shown as text
  await clickText("a", "Insights");
  await waitFor("document.body.textContent.includes('How replies were reviewed')", "insights");
  await sleep(300);
  await add(2400);
  await clickText("a", "Settings");
  await waitFor("document.body.textContent.includes('Your business')", "settings");
  await sleep(300);
  await add(2000);
  await press("?", { shift: true });
  await waitFor("document.querySelector('[role=dialog]')", "the shortcut list");
  await add(2600);
  const file = join(outDir, "walkthrough.png");
  writeFileSync(file, animatedPng(frames, delays));
  written.push(file);
}

async function freshStorage() {
  // Each width starts as a first visit: nothing typed or switched in an earlier pass carries over.
  await send("Storage.clearDataForOrigin", { origin: BASE, storageTypes: "all" });
}

try {
  await setViewport(1280, 800);
  if (phase === "walkthrough") {
    await setViewport(1280, 800);
    await freshStorage();
    await walkthrough();
  } else {
    for (const width of [1280, 360]) {
      await setViewport(width, width === 1280 ? 800 : 740);
      await freshStorage();
      if (phase === "demo") await demoStates(`${width}px`);
      else if (phase === "few") await fewStates();
      else await emptyStates();
    }
  }
  console.log(`wrote ${written.length} file(s) to ${outDir}`);
} finally {
  await browser.close();
}
