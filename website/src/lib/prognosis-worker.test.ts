import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { expect, it, vi } from "vitest";

// Exercise the real worker script with controlled assets and a minimal Python runtime double.
it("cleans request globals and recovers after a validation error", async () => {
  const messages: { type: string; id?: number }[] = [];
  const globals = new Map<string, unknown>();
  let listener: (event: { data: unknown }) => Promise<void> = async () => {};
  let valid = false;
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
    URL, JSON, Number, Promise,
    importScripts: vi.fn(), loadPyodide: async () => python,
    fetch: async () => ({ ok: true, text: async () => "{}" }),
    self: { location: { href: "http://localhost/prognosis-worker.js" },
      // Capture status and result messages emitted by the actual worker code.
      postMessage(message: { type: string; id?: number }) { messages.push(message); },
      // Preserve the worker's actual async request handler for subsequent synthetic requests.
      addEventListener(_name: string, handler: typeof listener) { listener = handler; }
    }
  });
  await vi.waitFor(() => expect(messages.some(message => message.type === "ready")).toBe(true));
  expect(globals.has("browser_model_text")).toBe(false);
  await listener({ data: { type: "analyse", id: 1, profile: {} } });
  expect(messages.at(-1)).toEqual({ type: "analysis-error", id: 1, message: "Invalid inputs." });
  expect(globals.has("browser_profile_text")).toBe(false);
  valid = true;
  await listener({ data: { type: "analyse", id: 2, profile: {} } });
  expect(messages.at(-1)?.type).toBe("result");
  expect(globals.has("browser_profile_text")).toBe(false);
});
