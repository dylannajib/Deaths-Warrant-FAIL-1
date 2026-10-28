import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const scripts = dirname(fileURLToPath(import.meta.url));

// List static files deterministically without following directory symlinks.
export function exportFiles(directory, prefix = "") {
  return readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap(entry => {
    if (entry.isSymbolicLink()) throw new Error("Export must not contain symlinks.");
    const name = prefix + entry.name;
    return entry.isDirectory() ? exportFiles(join(directory, entry.name), name + "/") : [name];
  });
}

// Hash the exact inline script text that a browser will receive, without executing it.
export function inlineHashes(html) {
  const document = new JSDOM(html).window.document;
  if (document.querySelector("[style], style")) throw new Error("Inline styles require an explicit reviewed CSP change.");
  for (const element of document.querySelectorAll("*")) {
    if (element.getAttributeNames().some(name => name.startsWith("on"))) throw new Error("Inline event attributes are unsupported.");
  }
  for (const element of document.querySelectorAll("script[src], link[href]")) {
    const url = element.getAttribute("src") ?? element.getAttribute("href");
    if (/^(https?:)?\/\//i.test(url)) throw new Error("Export contains an external script or stylesheet.");
  }
  return [...document.querySelectorAll("script:not([src])")].map(script =>
    "'sha256-" + createHash("sha256").update(script.textContent).digest("base64") + "'");
}

// Generate strict response headers and a file manifest for this exact static build.
export function finaliseExport(output = join(scripts, "../out")) {
  const files = exportFiles(output).filter(name => name !== "release.json");
  const hashes = [...new Set(files.filter(name => name.endsWith(".html")).flatMap(name => inlineHashes(readFileSync(join(output, name), "utf8"))))].sort();
  const policy = ["default-src 'none'", "base-uri 'none'", "object-src 'none'", "frame-ancestors 'none'",
    "form-action 'none'", "connect-src 'self'", "worker-src 'self'", "font-src 'self'", "img-src 'self'",
    "style-src 'self'", "style-src-attr 'none'", "script-src-attr 'none'",
    "script-src 'self' 'wasm-unsafe-eval' " + hashes.join(" ")].join("; ");
  const csp = "  Content-Security-Policy: " + policy;
  if (Buffer.byteLength(csp) > 2000) throw new Error("CSP exceeds the hosting header limit; split policy by route.");
  const baseline = readFileSync(join(scripts, "../public/_headers"), "utf8").trimEnd();
  const rules = [baseline, csp, ""];
  for (const path of ["/", "/*.html", "/prognosis-worker.js", "/prognosis/assets.json", "/release.json"]) {
    rules.push(path, "  Cache-Control: no-cache", "");
  }
  for (const path of ["/_next/static/*", "/vendor/pyodide/0.27.7/*", "/prognosis/engine.*.py", "/prognosis/model.*.json"]) {
    rules.push(path, "  Cache-Control: public, max-age=31536000, immutable", "");
  }
  writeFileSync(join(output, "_headers"), rules.join("\n"));
  const records = Object.fromEntries(files.map(name => {
    const path = join(output, name);
    return [name, { bytes: statSync(path).size, sha256: createHash("sha256").update(readFileSync(path)).digest("hex") }];
  }));
  const id = createHash("sha256").update(JSON.stringify(records)).digest("hex");
  writeFileSync(join(output, "release.json"), JSON.stringify({ schemaVersion: 1, id, files: records }, null, 2) + "\n");
  return { id, files: files.length, inlineScriptHashes: hashes.length };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(JSON.stringify(finaliseExport()));
}
