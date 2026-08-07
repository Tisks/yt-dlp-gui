// Simulates how Chrome's MV3 service worker and Firefox's background-page
// event page actually load these two files, to prove the importScripts guard
// in background.js really resolves FIRST_PORT/PORT_SPAN/APP_IDENTITY in both,
// not just that the syntax parses.
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const EXT_DIR = path.join(__dirname, "..", "chrome-extension");
const generatedSrc = fs.readFileSync(path.join(EXT_DIR, "generated_config.js"), "utf8");
const backgroundSrc = fs.readFileSync(path.join(EXT_DIR, "background.js"), "utf8");

function stubApi() {
  return {
    commands: { onCommand: { addListener: () => {} } },
    tabs: { query: async () => [] },
    storage: {
      local: {
        get: async () => ({}),
        set: async () => {},
        remove: async () => {},
      },
    },
  };
}

// `const` top-level bindings never become properties of the global object
// (per spec), even though later scripts in the same realm CAN still resolve
// them by identifier. So the only faithful way to check what background.js
// itself sees is to run one more snippet in the *same* context that captures
// the bare identifiers into a property Node can read back.
function probe(context) {
  vm.runInContext(
    "this.__probe = { FIRST_PORT, PORT_SPAN, APP_IDENTITY };",
    context,
    { filename: "probe.js" }
  );
  return context.__probe;
}

// --- Chrome path: only background.js is loaded; it must importScripts() ---
{
  const sandbox = { console, fetch: async () => ({ ok: false }) };
  sandbox.chrome = stubApi();
  sandbox.importScripts = (file) => {
    assert.strictEqual(file, "generated_config.js", "must request the generated file by its real name");
    vm.runInContext(generatedSrc, context, { filename: file });
  };
  const context = vm.createContext(sandbox);

  vm.runInContext(backgroundSrc, context, { filename: "background.js" });

  const values = probe(context);
  assert.strictEqual(values.FIRST_PORT, 5005, values.FIRST_PORT);
  assert.strictEqual(values.PORT_SPAN, 11, values.PORT_SPAN);
  assert.strictEqual(values.APP_IDENTITY, "yt-dlp-gui", values.APP_IDENTITY);
  console.log("TEST 1 PASSED: Chrome path (importScripts) resolves FIRST_PORT/PORT_SPAN/APP_IDENTITY");
}

// --- Firefox path: manifest's "scripts" array loads both files in order, ---
// --- sharing one global scope; background.js must NOT call importScripts ---
{
  const sandbox = { console, fetch: async () => ({ ok: false }) };
  sandbox.browser = stubApi();
  // No importScripts on this sandbox at all -- matches a real Firefox
  // background page, where the function simply doesn't exist.
  const context = vm.createContext(sandbox);

  // manifest.json lists generated_config.js before background.js.
  vm.runInContext(generatedSrc, context, { filename: "generated_config.js" });
  vm.runInContext(backgroundSrc, context, { filename: "background.js" });

  const values = probe(context);
  assert.strictEqual(values.FIRST_PORT, 5005, values.FIRST_PORT);
  assert.strictEqual(values.PORT_SPAN, 11, values.PORT_SPAN);
  assert.strictEqual(values.APP_IDENTITY, "yt-dlp-gui", values.APP_IDENTITY);
  console.log("TEST 2 PASSED: Firefox path (scripts array, no importScripts) resolves the same values");
}

// --- manifest.json actually lists them in the right order for Firefox -----
{
  const manifest = JSON.parse(fs.readFileSync(path.join(EXT_DIR, "manifest.json"), "utf8"));
  const scripts = manifest.background.scripts;
  assert.deepStrictEqual(scripts, ["generated_config.js", "background.js"], scripts);
  assert.strictEqual(manifest.background.service_worker, "background.js");
  console.log("TEST 3 PASSED: manifest.json background.scripts is [generated_config.js, background.js]");
}

console.log("ALL TESTS PASSED");
