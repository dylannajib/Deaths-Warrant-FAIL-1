import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { arch, platform, release, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { performance } from "node:perf_hooks";

const root = new URL("../../", import.meta.url);
const repetitions = 100;

// Summarise non-negative durations using nearest-rank percentiles in milliseconds.
export function summarise(samples) {
  if (!samples.length || samples.some(value => !Number.isFinite(value) || value < 0)) throw new Error("Invalid timing samples.");
  const sorted = [...samples].sort((a, b) => a - b);
  const total = samples.reduce((sum, value) => sum + value, 0);
  return { count: samples.length, totalMs: total, meanMs: total / samples.length, minMs: sorted[0],
    p50Ms: sorted[Math.ceil(sorted.length * 0.5) - 1], p95Ms: sorted[Math.ceil(sorted.length * 0.95) - 1], maxMs: sorted.at(-1) };
}

// Accept only documented options and resolve the optional static server without credentials or query strings.
export function readOptions(args) {
  const options = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    if (!["--base-url", "--output"].includes(key) || !args[index + 1] || Object.hasOwn(options, key)) {
      throw new Error("Usage: node scripts/benchmark-prognosis.mjs [--base-url URL] [--output PATH]");
    }
    options[key] = args[index + 1];
  }
  if (options["--base-url"]) {
    const url = new URL(options["--base-url"]);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error("Invalid static base URL.");
    options["--base-url"] = url.href.endsWith("/") ? url.href : url.href + "/";
  }
  return options;
}

// Reject non-finite means, uncertainty bounds or survival probabilities before recording successful inference.
export function assertReport(report) {
  const { lower, upper } = report.meanUncertainty;
  if (![report.remainingYears, lower, upper].every(value => Number.isFinite(value) && value > 0) || lower > upper ||
    !["1", "3", "5"].every(year => Number.isFinite(report.survivalByYear[year]) && report.survivalByYear[year] >= 0 && report.survivalByYear[year] <= 1)) {
    throw new Error("Inference returned an invalid estimate.");
  }
}

// Transpile the existing strict reader and its dependencies into a disposable Node module directory.
async function loadReader(directory) {
  const ts = (await import("typescript")).default;
  for (const name of ["fhir", "patient-profile", "cardiovascular-profile", "cardiovascular-fhir-profile"]) {
    const source = await readFile(new URL(`website/src/lib/${name}.ts`, root), "utf8");
    const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
    await writeFile(join(directory, name + ".mjs"), compiled.replace(/from "(\.\/[^".]+)"/g, 'from "$1.mjs"'));
  }
  return (await import(pathToFileURL(join(directory, "cardiovascular-fhir-profile.mjs")).href)).readFhirCardiovascularProfile;
}

// Time synchronous operations separately while allowing each operation to enforce its own correctness checks.
function repeat(operation, count = repetitions) {
  const samples = [];
  for (let index = 0; index < count; index++) {
    const start = performance.now(); operation(); samples.push(performance.now() - start);
  }
  return summarise(samples);
}

// Require an expected rejection so unsupported records cannot silently become benchmark successes.
function rejects(operation, pattern) {
  try { operation(); } catch (error) {
    if (pattern.test(String(error))) return;
    throw error;
  }
  throw new Error("Expected validation rejection was not raised.");
}

// Exercise one bounded batch of static asset fetches, including body consumption and individual deadlines.
export async function measureStatic(baseUrl) {
  const manifest = await fetch(new URL("prognosis/assets.json", baseUrl), { redirect: "error", signal: AbortSignal.timeout(15000) });
  if (!manifest.ok) throw new Error("Static prognosis manifest is unavailable.");
  const assets = await manifest.json();
  if (!/^model\.[a-f0-9]{64}\.json$/.test(assets.model)) throw new Error("Invalid static prognosis model path.");
  const url = new URL("prognosis/" + assets.model, baseUrl).href;
  const start = performance.now();
  const results = await Promise.all(Array.from({ length: 100 }, async () => {
    const began = performance.now();
    try {
      const response = await fetch(url, { redirect: "error", signal: AbortSignal.timeout(15000) });
      const bytes = (await response.arrayBuffer()).byteLength;
      return { code: String(response.status), bytes, ms: performance.now() - began };
    } catch { return { code: "network-error", bytes: 0, ms: performance.now() - began }; }
  }));
  const codes = {};
  for (const result of results) codes[result.code] = (codes[result.code] ?? 0) + 1;
  return { scope: "Local emulator static-asset proof only; not production users or capacity", asset: url,
    concurrency: 100, requests: 100, deadlineMs: 15000, wallMs: performance.now() - start, codes,
    allSuccessful: results.every(result => /^2\d\d$/.test(result.code)), bodyBytes: results.reduce((sum, result) => sum + result.bytes, 0),
    latency: summarise(results.map(result => result.ms)) };
}

// Benchmark the unchanged local inference engine and shared synthetic snapshot without loading participant data.
async function benchmark(options) {
  const paths = { engine: "src/deaths_warrant/cardiovascular_prognosis.py", model: "models/cardiovascular/model.json",
    profile: "tests/fixtures/cardiovascular/patient-profile.json", fhir: "tests/fixtures/cardiovascular/fhir.json" };
  const texts = Object.fromEntries(await Promise.all(Object.entries(paths).map(async ([key, path]) => [key, await readFile(new URL(path, root), "utf8")])));
  const profile = JSON.parse(texts.profile), model = JSON.parse(texts.model);
  const packageInfo = JSON.parse(await readFile(new URL("../node_modules/pyodide/package.json", import.meta.url), "utf8"));
  if (packageInfo.version !== "0.27.7") throw new Error("Benchmark requires pinned local Pyodide 0.27.7.");
  const started = performance.now();
  const { loadPyodide } = await import("pyodide");
  const python = await loadPyodide({ indexURL: fileURLToPath(new URL("../node_modules/pyodide/", import.meta.url)) });
  const runtimeMs = performance.now() - started;
  const engineStart = performance.now();
  python.runPython(texts.engine);
  python.globals.set("benchmark_model_text", texts.model);
  python.runPython("benchmark_model = validate_model(json.loads(benchmark_model_text))");
  python.globals.delete("benchmark_model_text");
  const engineModelMs = performance.now() - engineStart;
  let predictions = 0;
  // Include JSON bridging and serialisation in every inference, matching the worker's inference entry point.
  function analyse(value) {
    python.globals.set("benchmark_profile_text", JSON.stringify(value));
    try {
      const report = JSON.parse(python.runPython("json.dumps(predict_prognosis(json.loads(benchmark_profile_text), benchmark_model, research_mode=True), allow_nan=False)"));
      assertReport(report); predictions++; return report;
    } finally { python.globals.delete("benchmark_profile_text"); }
  }
  try {
    const firstPrediction = repeat(() => analyse(profile), 1);
    const warmPredictions = repeat(() => analyse(profile));
    const boundaryStart = performance.now();
    let boundaryCount = 0;
    for (const ageYears of [40, 79]) for (const recordedSex of [1, 2]) for (const endpoint of [0, 1]) {
      const boundary = { ...profile, ageYears, recordedSex };
      for (const [name, limits] of Object.entries(model.measurementRanges)) boundary[name] = limits[endpoint];
      analyse(boundary); boundaryCount++;
    }
    const boundaries = { supportedProfiles: boundaryCount, allEstimatesFinite: true, totalMs: performance.now() - boundaryStart };
    const invalid = [{ ...profile, ageYears: 39 }, { ...profile, ageYears: 80 }, { ...profile, recordedSex: 3 },
      { ...profile, diabetes: null }, { ...profile, creatinine: model.measurementRanges.creatinine[1] + 1 },
      { ...profile, heartFailure: false, angina: false }];
    const recoveryStart = performance.now();
    for (const value of invalid) { rejects(() => analyse(value), /ValueError/); analyse(profile); }
    const recovery = { rejectedProfiles: invalid.length, successfulRecoveries: invalid.length, totalMs: performance.now() - recoveryStart };
    const directory = await mkdtemp(join(tmpdir(), "dw-benchmark-"));
    let fhir;
    try {
      const readProfile = await loadReader(directory);
      // Compare fixture extraction without depending on JSON key ordering.
      function parseFixture() {
        const actual = readProfile(JSON.parse(texts.fhir), profile.asOf);
        if (Object.keys(actual).length !== Object.keys(profile).length || Object.keys(profile).some(key => actual[key] !== profile[key])) throw new Error("FHIR fixture parity failed.");
      }
      const fixture = repeat(parseFixture);
      const larger = JSON.parse(texts.fhir);
      while (larger.entry.length < 1001) larger.entry.push(structuredClone(larger.entry[1]));
      const largerText = JSON.stringify(larger);
      const duplicateRejection = repeat(() => rejects(() => readProfile(JSON.parse(largerText), profile.asOf), /Duplicate or conflicting/));
      parseFixture();
      fhir = { scope: "JSON.parse plus existing strict single-patient reader; not cohort support", fixtureBytes: Buffer.byteLength(texts.fhir),
        fixtureEntries: JSON.parse(texts.fhir).entry.length, fixture, duplicateEntries: larger.entry.length,
        duplicateBytes: Buffer.byteLength(largerText), duplicateRejection, validFixtureRecovery: true };
    } finally { await rm(directory, { recursive: true, force: true }); }
    return { schemaVersion: 1, measuredAt: new Date().toISOString(), scope: "Node Pyodide engine benchmark; not browser performance",
      environment: { node: process.version, pyodide: packageInfo.version, platform: platform(), release: release(), arch: arch() },
      inputs: Object.fromEntries(Object.entries(texts).map(([key, value]) => [key, { path: paths[key], bytes: Buffer.byteLength(value), sha256: createHash("sha256").update(value).digest("hex") }])),
      cold: { runtimeMs, engineModelMs, readyMs: runtimeMs + engineModelMs, firstPrediction }, warmPredictions, boundaries, recovery,
      successfulPredictions: predictions, allEstimatesFinite: true, fhir,
      ...(options["--base-url"] ? { staticRequests: await measureStatic(options["--base-url"]) } : {}) };
  } finally { python.globals.delete("benchmark_model"); }
}

// Write aggregate measurements only and keep stdout as a single machine-readable JSON document.
async function main() {
  const options = readOptions(process.argv.slice(2));
  const result = JSON.stringify(await benchmark(options), null, 2) + "\n";
  if (options["--output"]) await writeFile(resolve(options["--output"]), result);
  process.stdout.write(result);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  main().catch(error => { process.stderr.write(String(error) + "\n"); process.exitCode = 1; });
}
