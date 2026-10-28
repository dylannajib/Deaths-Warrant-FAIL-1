import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createHash, webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { expect, it, vi } from "vitest";

// Exercise the real worker script with controlled assets and a minimal Python runtime double.
it("cleans request globals and recovers after a validation error", async () => {
  const messages: { type: string; id?: number }[] = [];
  const globals = new Map<string, unknown>();
  let listener: (event: { data: unknown }) => Promise<void> = async () => {};
  let valid = false;
  const importRuntime = vi.fn(), loadRuntime = vi.fn();
  const assetUrls: string[] = [];
  const checksum = createHash("sha256").update("{}").digest("hex");
  const assets = { schemaVersion: 1, engine: "engine." + checksum + ".py", model: "model." + checksum + ".json" };
  const python = { globals: {
    // Record temporary Python values so cleanup can be asserted after each request.
    set(name: string, value: unknown) { globals.set(name, value); },
    // Remove the named temporary Python reference.
    delete(name: string) { globals.delete(name); }
  },
    // Return controlled bridge envelopes while allowing startup code to finish.
    async runPythonAsync(source: string) {
      if (source === "analyse_browser_profile(browser_profile_text)") return JSON.stringify(valid
        ? { ok: true, summary: { remainingYears: 10 } }
        : { ok: false, error: "Invalid inputs." });
      return undefined;
    }
  };
  runInNewContext(readFileSync("public/prognosis-worker.js", "utf8"), {
    URL, JSON, Number, Promise, TextEncoder, crypto: webcrypto,
    importScripts: importRuntime,
    // Capture the runtime directory passed to Python's loader.
    loadPyodide: async (options: unknown) => { loadRuntime(options); return python; },
    // Capture asset destinations without making real network requests in this unit test.
    fetch: async (url: URL) => {
      assetUrls.push(url.href);
      return { ok: true, text: async () => url.pathname.endsWith("assets.json") ? JSON.stringify(assets) : "{}" };
    },
    self: { location: { href: "http://localhost/prognosis-worker.js" },
      // Capture status and result messages emitted by the actual worker code.
      postMessage(message: { type: string; id?: number }) { messages.push(message); },
      // Preserve the worker's actual async request handler for subsequent synthetic requests.
      addEventListener(_name: string, handler: typeof listener) { listener = handler; }
    }
  });
  await vi.waitFor(() => expect(messages.some(message => message.type === "ready")).toBe(true));
  expect(importRuntime).toHaveBeenCalledWith("http://localhost/vendor/pyodide/0.27.7/pyodide.js");
  expect(loadRuntime).toHaveBeenCalledWith({ indexURL: "http://localhost/vendor/pyodide/0.27.7/" });
  expect(assetUrls).toEqual(["http://localhost/prognosis/assets.json",
    "http://localhost/prognosis/" + assets.engine, "http://localhost/prognosis/" + assets.model]);
  expect(globals.has("browser_model_text")).toBe(false);
  await listener({ data: { type: "analyse", id: 1, profile: {} } });
  expect(messages.at(-1)).toEqual({ type: "analysis-error", id: 1, message: "Invalid inputs." });
  expect(globals.has("browser_profile_text")).toBe(false);
  valid = true;
  await listener({ data: { type: "analyse", id: 2, profile: {} } });
  expect(messages.at(-1)?.type).toBe("result");
  expect(globals.has("browser_profile_text")).toBe(false);
});
