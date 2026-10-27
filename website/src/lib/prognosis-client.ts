import type { CardiovascularProfile } from "./cardiovascular-profile";

export type PrognosisReport = {
  modelVersion: string; status: "experimental"; clinicallyValidated: false;
  asOf: string; remainingYears: number; survivalByYear: Record<"1" | "3" | "5", number>;
  meanUncertainty: { lower: number; upper: number; level: number; samples: number; meaning: string };
  supportsTreatmentEffects: false; supportsConditionAttribution: false; warnings: string[];
};
export type WorkerState = { phase: "loading" | "ready" | "error"; message: string };

// Reject malformed runtime messages before any result reaches the React display.
function readReport(value: unknown): PrognosisReport {
  if (!value || typeof value !== "object") throw new Error("Invalid prognosis response.");
  const report = value as PrognosisReport;
  const interval = report.meanUncertainty;
  if (report.modelVersion !== "nhanes-cardiovascular-weibull-0.1.0" || report.status !== "experimental" ||
    report.clinicallyValidated !== false || report.supportsTreatmentEffects !== false ||
    report.supportsConditionAttribution !== false || typeof report.asOf !== "string" ||
    !Number.isFinite(report.remainingYears) || report.remainingYears <= 0 ||
    !report.survivalByYear || !["1", "3", "5"].every(year => {
      const probability = report.survivalByYear[year as "1" | "3" | "5"];
      return Number.isFinite(probability) && probability >= 0 && probability <= 1;
    }) || !interval || !Number.isFinite(interval.lower) || !Number.isFinite(interval.upper) ||
    interval.lower <= 0 || interval.upper < interval.lower || interval.level !== 0.95 ||
    !Number.isInteger(interval.samples) || interval.samples < 30 || typeof interval.meaning !== "string" ||
    !Array.isArray(report.warnings) || !report.warnings.every(message => typeof message === "string")) {
    throw new Error("Invalid prognosis response.");
  }
  if (report.survivalByYear["5"] > report.survivalByYear["3"] || report.survivalByYear["3"] > report.survivalByYear["1"]) {
    throw new Error("Invalid survival probabilities.");
  }
  return report;
}

// Own one worker, reject stale replies and terminate stalled or failed runtime instances.
export function createPrognosisClient(onState: (state: WorkerState) => void, worker: Worker = new Worker("./prognosis-worker.js")) {
  let ready = false, disposed = false, nextId = 0;
  let pending: { id: number; asOf: string; resolve: (report: PrognosisReport) => void; reject: (error: Error) => void } | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  // Clear whichever startup or calculation deadline is currently active.
  function clearDeadline() {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  }

  // End this runtime and settle any calculation that would otherwise remain pending.
  function fail(message: string) {
    if (disposed) return;
    disposed = true; ready = false; clearDeadline(); worker.terminate();
    pending?.reject(new Error(message)); pending = null;
    onState({ phase: "error", message });
  }

  // Process only the current request ID so late replies cannot replace a newer result.
  function handleMessage(event: MessageEvent) {
    if (disposed || !event.data || typeof event.data !== "object") return;
    const message = event.data;
    if (message.type === "loading" && !ready) {
      onState({ phase: "loading", message: typeof message.message === "string" ? message.message : "Loading..." });
    } else if (message.type === "ready") {
      if (ready) return;
      ready = true; clearDeadline(); onState({ phase: "ready", message: "Prognosis model ready." });
    } else if (message.type === "startup-error") {
      fail("Prognosis startup failed. Retry to start a new worker.");
    } else if (pending && message.id === pending.id && ["result", "analysis-error"].includes(message.type)) {
      const request = pending; pending = null; clearDeadline();
      if (message.type === "analysis-error") {
        request.reject(new Error(typeof message.message === "string" ? message.message : "Analysis failed."));
      } else {
        try {
          const report = readReport(message.report);
          if (report.asOf !== request.asOf) throw new Error("Assessment date changed in the response.");
          request.resolve(report);
        } catch {
          request.reject(new Error("The worker returned an invalid prognosis result."));
        }
      }
    }
  }

  // Stop the worker after a browser runtime error or an unreadable message.
  function handleError() {
    fail("The prognosis worker stopped. Retry to start a new worker.");
  }

  // Refuse concurrent requests and limit each local calculation to thirty seconds.
  function predict(profile: CardiovascularProfile): Promise<PrognosisReport> {
    if (!ready || disposed) return Promise.reject(new Error("Wait for the prognosis model to become ready."));
    if (pending) return Promise.reject(new Error("A calculation is already running."));
    return new Promise((resolve, reject) => {
      const id = ++nextId;
      pending = { id, asOf: profile.asOf, resolve, reject };
      timer = setTimeout(() => fail("Calculation timed out. Retry to start a new worker."), 30000);
      try { worker.postMessage({ type: "analyse", id, profile }); }
      catch { fail("Could not start the calculation. Retry the worker."); }
    });
  }

  // Terminate the worker when the page closes, clears the record or starts a replacement.
  function dispose() {
    if (disposed) return;
    disposed = true; ready = false; clearDeadline(); worker.terminate();
    pending?.reject(new Error("Calculation cancelled.")); pending = null;
  }

  worker.addEventListener("message", handleMessage);
  worker.addEventListener("error", handleError);
  worker.addEventListener("messageerror", handleError);
  timer = setTimeout(() => fail("Startup timed out. Check your connection and retry."), 90000);
  return { predict, dispose };
}
