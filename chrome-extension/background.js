// FIRST_PORT, PORT_SPAN and APP_IDENTITY come from generated_config.js, kept in
// sync with config.py by scripts/generate_extension_config.py. Firefox loads it
// first via manifest.json's "scripts" array (shared global scope); Chrome's
// service worker only loads this one file, so it pulls generated_config.js in
// itself via importScripts, which MV3 supports for non-module service workers.
if (typeof importScripts === "function" && typeof FIRST_PORT === "undefined") {
  importScripts("generated_config.js");
}

const api = typeof browser !== "undefined" ? browser : chrome;

const HOST = "http://127.0.0.1";
const PORT_CACHE_KEY = "appPort";

// The app binds the first free port in this range, so we probe the same range.
const PORTS = Array.from({ length: PORT_SPAN }, (_, index) => FIRST_PORT + index);

function endpoint(port, path) {
  return `${HOST}:${port}${path}`;
}

function detectBrowser() {
  if (typeof browser !== "undefined") return "firefox";
  const ua = navigator.userAgent;
  if (ua.includes("OPR/") || ua.includes("Opera")) return "opera";
  return "chrome";
}

// A port being open is not enough -- it has to be *our* app answering.
async function isOurApp(port) {
  try {
    const response = await fetch(endpoint(port, "/ping"), { method: "GET" });
    if (!response.ok) return false;
    const data = await response.json();
    return data.app === APP_IDENTITY;
  } catch (error) {
    return false;
  }
}

async function readCachedPort() {
  try {
    const stored = await api.storage.local.get(PORT_CACHE_KEY);
    const port = stored[PORT_CACHE_KEY];
    return typeof port === "number" ? port : null;
  } catch (error) {
    return null;
  }
}

async function writeCachedPort(port) {
  try {
    if (port === null) {
      await api.storage.local.remove(PORT_CACHE_KEY);
    } else {
      await api.storage.local.set({ [PORT_CACHE_KEY]: port });
    }
  } catch (error) {
    // A cache miss just means we rescan next time; not worth failing over.
  }
}

async function discoverPort() {
  const cached = await readCachedPort();
  if (cached !== null && (await isOurApp(cached))) return cached;

  for (const port of PORTS) {
    if (port === cached) continue;
    if (await isOurApp(port)) {
      console.log("[yt-dlp-gui] found app on port", port);
      await writeCachedPort(port);
      return port;
    }
  }

  console.warn(`[yt-dlp-gui] app not reachable on ports ${PORTS[0]}-${PORTS[PORTS.length - 1]}`);
  await writeCachedPort(null);
  return null;
}

async function post(path, body) {
  const port = await discoverPort();
  if (port === null) return;

  const options = { method: "POST" };
  if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(endpoint(port, path), options);
    console.log("[yt-dlp-gui]", path, "->", response.status);
  } catch (error) {
    // The app went away between the ping and this call; rescan next time.
    console.error("[yt-dlp-gui]", path, "failed:", error);
    await writeCachedPort(null);
  }
}

async function sendActiveTabUrl() {
  const tabs = await api.tabs.query({ active: true, currentWindow: true });
  const url = tabs[0]?.url;
  if (!url) {
    console.warn("[yt-dlp-gui] no url on active tab, aborting send-url", tabs[0]);
    return;
  }
  await post("/url", { url, browser: detectBrowser() });
}

api.commands.onCommand.addListener((command) => {
  console.log("[yt-dlp-gui] command:", command);
  if (command === "send-url") {
    sendActiveTabUrl().catch((error) => console.error("[yt-dlp-gui] send-url failed:", error));
  } else if (command === "trigger-download") {
    post("/download").catch(() => {});
  } else if (command === "check-archive") {
    post("/check-archive").catch(() => {});
  }
});
