import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { exportFiles, inlineHashes } from "./finalise-export.mjs";

const scripts = dirname(fileURLToPath(import.meta.url));

// Refuse corrupted, oversized or unexpectedly expanded releases before deployment.
export function checkExport(output = join(scripts, "../out")) {
  const release = JSON.parse(readFileSync(join(output, "release.json"), "utf8"));
  const files = exportFiles(output).filter(name => name !== "release.json");
  if (release.schemaVersion !== 1 || JSON.stringify(files) !== JSON.stringify(Object.keys(release.files))) throw new Error("Export file list changed.");
  const id = createHash("sha256").update(JSON.stringify(release.files)).digest("hex");
  if (id !== release.id) throw new Error("Release manifest fingerprint mismatch.");
  const headers = readFileSync(join(output, "_headers"), "utf8");
  if (headers.includes("'unsafe-inline'") || headers.includes("'unsafe-eval'") || !headers.includes("connect-src 'self'")) throw new Error("Unsafe or missing CSP.");
  const required = ["index.html", "404.html", "_headers", "prognosis-worker.js", "prognosis/assets.json"];
  for (const name of required) if (!files.includes(name)) throw new Error("Required export file missing: " + name);
  const runtime = JSON.parse(readFileSync(join(scripts, "pyodide-manifest.json"), "utf8"));
  // Check deployed runtime bytes against the pinned source manifest, not just the new release inventory.
  for (const [name, expected] of Object.entries(runtime.files)) {
    const path = "vendor/pyodide/" + runtime.version + "/" + name;
    if (!files.includes(path)) throw new Error("Required runtime file missing: " + name);
    const actual = createHash("sha256").update(readFileSync(join(output, path))).digest("hex");
    if (actual !== expected) throw new Error("Exported runtime checksum mismatch: " + name);
  }
  for (const name of files) {
    if (/(^|\/)(data|tests|src|\.git|node_modules)(\/|$)/.test(name) || /\.(csv|xpt|dat|env|pyc)$/i.test(name)) throw new Error("Unexpected private/development export: " + name);
    const contents = readFileSync(join(output, name));
    const record = release.files[name];
    if (contents.length > 25 * 1024 * 1024) throw new Error("Export file exceeds host size limit: " + name);
    if (contents.length !== record.bytes || createHash("sha256").update(contents).digest("hex") !== record.sha256) throw new Error("Export file changed: " + name);
    if (name.endsWith(".html")) {
      for (const hash of inlineHashes(contents.toString("utf8"))) if (!headers.includes(hash)) throw new Error("Missing inline script CSP hash.");
    }
  }
  const assets = JSON.parse(readFileSync(join(output, "prognosis/assets.json"), "utf8"));
  for (const [key, extension] of [["engine", "py"], ["model", "json"]]) {
    if (!new RegExp("^" + key + "\\.[a-f0-9]{64}\\." + extension + "$").test(assets[key])) throw new Error("Invalid prognosis manifest.");
    const hash = createHash("sha256").update(readFileSync(join(output, "prognosis", assets[key]))).digest("hex");
    if (hash !== assets[key].split(".")[1]) throw new Error("Content-addressed prognosis asset changed.");
  }
  const model = JSON.parse(readFileSync(join(output, "prognosis", assets.model), "utf8"));
  const frozen = JSON.parse(readFileSync(join(scripts, "../../models/cardiovascular/model.json"), "utf8"));
  if (JSON.stringify(model) !== JSON.stringify(frozen)) throw new Error("Export differs from the frozen model.");
  return { id, files: files.length, checked: true };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(JSON.stringify(checkExport()));
