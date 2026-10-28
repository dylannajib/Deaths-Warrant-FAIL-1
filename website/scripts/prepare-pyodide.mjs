import { copyFileSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scripts = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(scripts, "pyodide-manifest.json"), "utf8"));

// Verify the locked runtime before copying the minimum files and notices into the static site.
export function preparePyodide(source = join(scripts, "../node_modules/pyodide"),
  destination = join(scripts, "../public/vendor/pyodide", manifest.version)) {
  const metadata = JSON.parse(readFileSync(join(source, "package.json"), "utf8"));
  const lock = JSON.parse(readFileSync(join(scripts, "../package-lock.json"), "utf8"));
  if (metadata.version !== manifest.version || lock.packages["node_modules/pyodide"]?.integrity !== manifest.packageIntegrity) {
    throw new Error("Pyodide version or locked package integrity differs from the approved runtime.");
  }
  // Verify every source first so a mismatch cannot leave a partly updated runtime.
  for (const [name, expected] of Object.entries(manifest.files)) {
    const actual = createHash("sha256").update(readFileSync(join(source, name))).digest("hex");
    if (actual !== expected) throw new Error("Pyodide file checksum mismatch: " + name);
  }
  mkdirSync(destination, { recursive: true });
  for (const name of Object.keys(manifest.files)) copyFileSync(join(source, name), join(destination, name));
  const notices = join(scripts, "../vendor-notices/pyodide-" + manifest.version);
  for (const name of readdirSync(notices)) copyFileSync(join(notices, name), join(destination, name));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) preparePyodide();
