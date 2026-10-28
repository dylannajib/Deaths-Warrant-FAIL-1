const runtime = new URL("vendor/pyodide/0.27.7/", self.location.href).href;
let python = null, busy = false;

// Fetch application code or coefficients and reject failed HTTP responses.
async function readAsset(name) {
  const response = await fetch(new URL("prognosis/" + name, self.location.href),
    { cache: name === "assets.json" ? "no-store" : "default" });
  if (!response.ok) throw new Error("Could not load a required prognosis asset.");
  const text = await response.text();
  if (name !== "assets.json") {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    const actual = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
    if (actual !== name.split(".")[1]) throw new Error("Prognosis asset checksum mismatch.");
  }
  return text;
}

// Load Python once and keep only the frozen model as a persistent Python global.
async function initialise() {
  try {
    self.postMessage({ type: "loading", message: "Loading browser Python..." });
    importScripts(runtime + "pyodide.js");
    python = await loadPyodide({ indexURL: runtime });
    self.postMessage({ type: "loading", message: "Loading the prognosis model..." });
    const assets = JSON.parse(await readAsset("assets.json"));
    if (assets.schemaVersion !== 1 || !/^engine\.[a-f0-9]{64}\.py$/.test(assets.engine) ||
      !/^model\.[a-f0-9]{64}\.json$/.test(assets.model)) throw new Error("Unsupported prognosis asset manifest.");
    const [source, model] = await Promise.all([readAsset(assets.engine), readAsset(assets.model)]);
    await python.runPythonAsync(source);
    python.globals.set("browser_model_text", model);
    try {
      await python.runPythonAsync(`
browser_model = validate_model(json.loads(browser_model_text))

# Return readable validation errors while keeping patient inputs out of persistent globals.
def analyse_browser_profile(profile_text):
    try:
        profile = json.loads(profile_text)
        report = predict_prognosis(profile, browser_model, research_mode = True)
        return json.dumps({"ok": True, "summary": report}, allow_nan = False)
    except ValueError as error:
        return json.dumps({"ok": False, "error": str(error)})
    except ArithmeticError:
        return json.dumps({"ok": False, "error": "The model could not calculate a finite estimate for these inputs."})
`);
    } finally {
      python.globals.delete("browser_model_text");
    }
    self.postMessage({ type: "ready" });
  } catch {
    self.postMessage({ type: "startup-error", message: "Prognosis startup failed. Retry to start a new worker." });
  }
}

// Run one validated profile request at a time and drop its temporary Python reference afterwards.
async function handleMessage(event) {
  const request = event.data;
  if (!request || request.type !== "analyse" || !Number.isSafeInteger(request.id)) return;
  if (!python || busy) {
    self.postMessage({ type: "analysis-error", id: request.id, message: "The prognosis worker is not ready." });
    return;
  }
  busy = true;
  try {
    const text = JSON.stringify(request.profile);
    if (typeof text !== "string" || text.length > 16384) throw new Error("Unsupported profile request.");
    python.globals.set("browser_profile_text", text);
    const result = JSON.parse(await python.runPythonAsync("analyse_browser_profile(browser_profile_text)"));
    if (result.ok === true) self.postMessage({ type: "result", id: request.id, report: result.summary });
    else self.postMessage({ type: "analysis-error", id: request.id, message: result.error });
  } catch {
    self.postMessage({ type: "analysis-error", id: request.id, message: "The calculation could not finish. Check the inputs or retry." });
  } finally {
    if (python) python.globals.delete("browser_profile_text");
    busy = false;
  }
}

self.addEventListener("message", handleMessage);
initialise();
