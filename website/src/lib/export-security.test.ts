import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { afterEach, expect, it } from "vitest";
import { finaliseExport, inlineHashes } from "../../scripts/finalise-export.mjs";
import { checkExport } from "../../scripts/check-export.mjs";

const temporary: string[] = [];

// Build a minimal synthetic export with the exact frozen model but no participant records.
function fixture() {
  const directory = mkdtempSync(join(tmpdir(), "dw-export-")); temporary.push(directory);
  mkdirSync(join(directory, "prognosis"));
  const runtime = JSON.parse(readFileSync("scripts/pyodide-manifest.json", "utf8"));
  const vendor = join(directory, "vendor/pyodide", runtime.version);
  mkdirSync(vendor, { recursive: true });
  for (const name of Object.keys(runtime.files)) copyFileSync(join("node_modules/pyodide", name), join(vendor, name));
  for (const name of ["index.html", "404.html"]) writeFileSync(join(directory, name), "<!doctype html><script>self.test=1</script>");
  writeFileSync(join(directory, "_headers"), "/*\n");
  writeFileSync(join(directory, "prognosis-worker.js"), "// synthetic worker\n");
  const assets = { schemaVersion: 1, engine: "", model: "" };
  for (const [key, extension, source] of [["engine", "py", "../src/deaths_warrant/cardiovascular_prognosis.py"],
    ["model", "json", "../models/cardiovascular/model.json"]] as const) {
    const contents = readFileSync(source);
    const name = key + "." + createHash("sha256").update(contents).digest("hex") + "." + extension;
    assets[key] = name; writeFileSync(join(directory, "prognosis", name), contents);
  }
  writeFileSync(join(directory, "prognosis/assets.json"), JSON.stringify(assets));
  return { directory, assets };
}

// Remove only this suite's unique temporary export directories.
afterEach(() => { for (const path of temporary.splice(0)) rmSync(path, { recursive: true, force: true }); });

// Allow the exact generated startup script while rejecting blanket inline-script permission.
it("generates and validates strict CSP and cache rules", () => {
  const { directory } = fixture();
  finaliseExport(directory);
  expect(checkExport(directory).checked).toBe(true);
  const headers = readFileSync(join(directory, "_headers"), "utf8");
  expect(headers).toContain(inlineHashes("<script>self.test=1</script>")[0]);
  expect(headers).not.toContain("'unsafe-inline'");
  expect(headers).not.toContain("'unsafe-eval'");
  expect(headers).toContain("connect-src 'self'");
  expect(headers).toContain("/prognosis/assets.json\n  Cache-Control: no-cache");
  expect(headers).toContain("/prognosis/model.*.json\n  Cache-Control: public, max-age=31536000, immutable");
});

// Changing even one exported byte invalidates the prepared release.
it("detects modified files after finalisation", () => {
  const { directory } = fixture(); finaliseExport(directory);
  writeFileSync(join(directory, "index.html"), "changed after build");
  expect(() => checkExport(directory)).toThrow(/changed/);
});

// Recreating the release inventory must not approve a changed upstream runtime.
it("rejects modified runtime bytes even after manifest regeneration", () => {
  const { directory } = fixture();
  writeFileSync(join(directory, "vendor/pyodide/0.27.7/pyodide.js"), "// corrupted runtime");
  finaliseExport(directory);
  expect(() => checkExport(directory)).toThrow(/runtime checksum/);
});

// Missing browser Python files are deployment failures even if no HTML references them directly.
it("requires every pinned runtime file", () => {
  const { directory } = fixture();
  unlinkSync(join(directory, "vendor/pyodide/0.27.7/pyodide.asm.wasm"));
  finaliseExport(directory);
  expect(() => checkExport(directory)).toThrow(/runtime file missing/);
});

// Extra data files must be rejected even if someone regenerates the release manifest.
it("refuses participant-style exports", () => {
  const { directory } = fixture();
  writeFileSync(join(directory, "synthetic.csv"), "fictional-only"); finaliseExport(directory);
  expect(() => checkExport(directory)).toThrow(/private\/development/);
});

// Reject unsupported event attributes, inline styling and third-party executable resources.
it.each(["<p style='color:red'>x</p>", "<style>body{color:red}</style>",
  "<button onclick='run()'>x</button>", "<script src='https://example.invalid/code.js'></script>"])("rejects unsafe HTML: %s", html => {
  expect(() => inlineHashes(html)).toThrow();
});

// Keep manifest-controlled asset paths inside the generated prognosis directory.
it("rejects a traversal path in the prognosis manifest", () => {
  const { directory, assets } = fixture();
  writeFileSync(join(directory, "prognosis/assets.json"), JSON.stringify({ ...assets, engine: "../../engine.py" }));
  finaliseExport(directory);
  expect(() => checkExport(directory)).toThrow(/manifest/);
});
