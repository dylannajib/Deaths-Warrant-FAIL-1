import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const output = new URL("../public/prognosis/", import.meta.url);
mkdirSync(output, { recursive: true });
// Ship the frozen model and inference source; training data and fitting libraries stay offline.
for (const [source, name] of [
  ["../../models/cardiovascular/model.json", "model.json"],
  ["../../src/deaths_warrant/cardiovascular_prognosis.py", "engine.py"]
]) copyFileSync(fileURLToPath(new URL(source, import.meta.url)), fileURLToPath(new URL(name, output)));
