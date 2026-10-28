import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const root = new URL("../../", import.meta.url);
const folder = new URL("data/manual-testing/published/mimic-iv-fhir-demo-2.1.0/", root);

// Run the actual website reader against every locally collected cardiovascular patient excerpt.
async function main() {
  const audit = JSON.parse(await readFile(new URL("cardiovascular-audit.json", folder), "utf8"));
  const directory = await mkdtemp(join(tmpdir(), "dw-mimic-reader-"));
  try {
    const ts = (await import("typescript")).default;
    for (const name of ["fhir", "patient-profile", "cardiovascular-profile", "cardiovascular-fhir-profile"]) {
      const source = await readFile(new URL(`website/src/lib/${name}.ts`, root), "utf8");
      const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
      await writeFile(join(directory, name + ".mjs"), compiled.replace(/from "(\.\/[^".]+)"/g, 'from "$1.mjs"'));
    }
    const { readFhirCardiovascularProfile } = await import(pathToFileURL(join(directory, "cardiovascular-fhir-profile.mjs")).href);
    const results = [];
    for (const patient of audit.records) {
      const bundle = JSON.parse(await readFile(new URL("all-cardiovascular/" + patient.file, folder), "utf8"));
      try {
        const profile = readFhirCardiovascularProfile(bundle, patient.asOf);
        results.push({ subjectId: patient.subjectId, accepted: true, profile });
      } catch (error) {
        if (!(error instanceof Error)) throw error;
        results.push({ subjectId: patient.subjectId, accepted: false, error: error.message });
      }
    }
    const summary = { tested: results.length, accepted: results.filter(result => result.accepted).length,
      rejected: results.filter(result => !result.accepted).length,
      meaning: "Import compatibility check only. Rejection is not a prognosis prediction or a mortality accuracy result." };
    await writeFile(new URL("import-results.json", folder), JSON.stringify({ summary, results }, null, 2) + "\n");
    console.log(JSON.stringify({ ...summary, output: fileURLToPath(new URL("import-results.json", folder)) }));
  } finally { await rm(directory, { recursive: true, force: true }); }
}

main().catch(error => { console.error(String(error)); process.exitCode = 1; });
