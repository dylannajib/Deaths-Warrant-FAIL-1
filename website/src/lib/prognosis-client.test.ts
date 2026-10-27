import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { createPrognosisClient } from "./prognosis-client";

const profile = JSON.parse(readFileSync("../tests/fixtures/cardiovascular/patient-profile.json", "utf8"));

// Capture requests and supply controlled replies without starting a real Python runtime.
class TestWorker extends EventTarget {
  requests: unknown[] = [];
  // Keep each outbound request available for ID and payload assertions.
  postMessage(value: unknown) { this.requests.push(value); }
  // Record worker termination after cleanup, failure or timeout.
  terminate = vi.fn();
  // Deliver a synthetic worker reply through the same event path as the browser.
  reply(value: unknown) { this.dispatchEvent(new MessageEvent("message", { data: value })); }
}

// Provide a finite, structurally valid result independent of any fitted coefficients.
function result() {
  return { modelVersion: "nhanes-cardiovascular-weibull-0.1.0", status: "experimental", clinicallyValidated: false,
    asOf: profile.asOf, remainingYears: 10, survivalByYear: { "1": 0.9, "3": 0.7, "5": 0.5 },
    meanUncertainty: { lower: 8, upper: 12, level: 0.95, samples: 100, meaning: "Fitted mean only." },
    supportsTreatmentEffects: false, supportsConditionAttribution: false, warnings: ["Research estimate."] };
}

// Start each test with controlled deadlines rather than waiting ninety real seconds.
beforeEach(() => { vi.useFakeTimers(); });
// Restore normal timers so this suite cannot alter another suite's behaviour.
afterEach(() => { vi.useRealTimers(); });

// Match responses by request ID and keep worker messages free of raw record text.
it("resolves only the current matching request", async () => {
  const worker = new TestWorker(), client = createPrognosisClient(vi.fn(), worker as unknown as Worker);
  worker.reply({ type: "ready" });
  const pending = client.predict(profile);
  expect(worker.requests[0]).toEqual({ type: "analyse", id: 1, profile });
  worker.reply({ type: "result", id: 999, report: result() });
  worker.reply({ type: "result", id: 1, report: result() });
  await expect(pending).resolves.toEqual(result());
  client.dispose();
});

// Invalid replies must reject cleanly rather than becoming displayed estimates.
it("rejects malformed model output", async () => {
  const worker = new TestWorker(), client = createPrognosisClient(vi.fn(), worker as unknown as Worker);
  worker.reply({ type: "ready" });
  const pending = client.predict(profile);
  worker.reply({ type: "result", id: 1, report: { ...result(), remainingYears: Infinity } });
  await expect(pending).rejects.toThrow(/invalid prognosis/);
  client.dispose();
});

// Startup deadlines terminate their worker and tell the page to offer retry.
it("terminates a stalled startup", () => {
  const worker = new TestWorker(), state = vi.fn();
  createPrognosisClient(state, worker as unknown as Worker);
  vi.advanceTimersByTime(90000);
  expect(worker.terminate).toHaveBeenCalledOnce();
  expect(state).toHaveBeenLastCalledWith(expect.objectContaining({ phase: "error" }));
});

// Refuse overlapping calculations and settle an interrupted request when the page clears.
it("rejects concurrency and cancels on disposal", async () => {
  const worker = new TestWorker(), client = createPrognosisClient(vi.fn(), worker as unknown as Worker);
  worker.reply({ type: "ready" });
  const first = client.predict(profile);
  await expect(client.predict(profile)).rejects.toThrow(/already running/);
  const cancelled = expect(first).rejects.toThrow(/cancelled/);
  client.dispose();
  await cancelled;
  expect(worker.terminate).toHaveBeenCalledOnce();
});

// A timed-out calculation must not remain pending or reuse its broken runtime.
it("terminates an overdue calculation", async () => {
  const worker = new TestWorker(), client = createPrognosisClient(vi.fn(), worker as unknown as Worker);
  worker.reply({ type: "ready" });
  const rejected = expect(client.predict(profile)).rejects.toThrow(/timed out/);
  vi.advanceTimersByTime(30000);
  await rejected;
  expect(worker.terminate).toHaveBeenCalledOnce();
});
