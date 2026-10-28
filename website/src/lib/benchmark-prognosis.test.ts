import { afterEach, expect, it, vi } from "vitest";
import { assertReport, measureStatic, readOptions, summarise } from "../../scripts/benchmark-prognosis.mjs";

// Restore the native fetch implementation after the isolated static-load test.
afterEach(() => { vi.unstubAllGlobals(); });

// Keep timing summaries ordered, finite and independent of the caller's input array.
it("summarises unordered durations and rejects unusable measurements", () => {
  const values = [9, 0, 2, 1];
  expect(summarise(values)).toMatchObject({ count: 4, totalMs: 12, meanMs: 3, minMs: 0, p50Ms: 1, p95Ms: 9, maxMs: 9 });
  expect(values).toEqual([9, 0, 2, 1]);
  for (const invalid of [[], [NaN], [Infinity], [-1]]) expect(() => summarise(invalid)).toThrow();
});

// Reject ambiguous command lines and URLs that would expose credentials in aggregate output.
it("accepts explicit options and rejects missing, repeated or unsafe arguments", () => {
  expect(readOptions(["--base-url", "http://127.0.0.1:8004", "--output", "../docs/performance-results.json"]))
    .toEqual({ "--base-url": "http://127.0.0.1:8004/", "--output": "../docs/performance-results.json" });
  for (const args of [["--output"], ["--repeat", "1000"], ["--output", "a", "--output", "b"],
    ["--base-url", "file:///tmp/"], ["--base-url", "http://secret@example.com/"], ["--base-url", "http://localhost/?token=x"]]) {
    expect(() => readOptions(args)).toThrow();
  }
});

// Detect invalid uncertainty and survival output even when the central estimate is finite.
it("requires finite positive means and uncertainty with bounded survival probabilities", () => {
  const report = { remainingYears: 10, meanUncertainty: { lower: 8, upper: 12 }, survivalByYear: { 1: 0.9, 3: 0.8, 5: 0.7 } };
  expect(() => assertReport(report)).not.toThrow();
  for (const invalid of [{ ...report, remainingYears: Infinity }, { ...report, meanUncertainty: { lower: 12, upper: 8 } },
    { ...report, meanUncertainty: { lower: NaN, upper: 12 } }, { ...report, survivalByYear: { 1: 0.9, 3: 0.8, 5: 1.1 } }]) {
    expect(() => assertReport(invalid)).toThrow();
  }
});

// Verify the fixed static batch consumes bodies and reports HTTP failures separately from network failures.
it("limits static work to 100 model fetches and accounts for every result", async () => {
  let calls = 0, bodies = 0;
  const filename = "model." + "a".repeat(64) + ".json";
  vi.stubGlobal("fetch", vi.fn(async (url: string | URL, options: RequestInit) => {
    expect(options.redirect).toBe("error");
    expect(options.signal).toBeDefined();
    if (String(url).endsWith("assets.json")) return { ok: true, json: async () => ({ model: filename }) };
    expect(url).toBe("http://127.0.0.1:8004/prognosis/" + filename);
    const index = calls++;
    if (index === 0) throw new Error("offline");
    return { status: index === 1 ? 404 : 200, arrayBuffer: async () => { bodies++; return new ArrayBuffer(5); } };
  }));
  const result = await measureStatic("http://127.0.0.1:8004/");
  expect(calls).toBe(100);
  expect(bodies).toBe(99);
  expect(result).toMatchObject({ concurrency: 100, requests: 100, allSuccessful: false, bodyBytes: 495,
    codes: { "200": 98, "404": 1, "network-error": 1 }, latency: { count: 100 } });
});
