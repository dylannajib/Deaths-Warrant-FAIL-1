import { mkdirSync, readFileSync, readdirSync, unlinkSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { preparePyodide } from "./prepare-pyodide.mjs";

preparePyodide();

const output = new URL("../public/prognosis/", import.meta.url);
mkdirSync(output, { recursive: true });
// Remove only recognised generated files so previous builds cannot ship stale model copies.
for (const name of readdirSync(output)) {
  if (!/^(assets\.json|engine(?:\.[a-f0-9]{64})?\.py|model(?:\.[a-f0-9]{64})?\.json)$/.test(name)) {
    throw new Error("Unexpected file in generated prognosis directory: " + name);
  }
  unlinkSync(new URL(name, output));
}
const assets = { schemaVersion: 1 };
// Ship the frozen model and inference source; training data and fitting libraries stay offline.
for (const [source, name] of [
  ["../../models/cardiovascular/model.json", "model.json"],
  ["../../src/deaths_warrant/cardiovascular_prognosis.py", "engine.py"]
]) {
  const contents = readFileSync(fileURLToPath(new URL(source, import.meta.url)));
  const hash = createHash("sha256").update(contents).digest("hex");
  const [stem, extension] = name.split(".");
  const filename = stem + "." + hash + "." + extension;
  assets[stem] = filename;
  writeFileSync(new URL(filename, output), contents);
}
writeFileSync(new URL("assets.json", output), JSON.stringify(assets, null, 2) + "\n");
