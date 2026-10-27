"use client";

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { validatePatientFile } from "@/lib/patient-file";
import { readFhirCardiovascularEvidence } from "@/lib/cardiovascular-fhir-profile";
import { readCcdCardiovascularEvidence } from "@/lib/cardiovascular-ccda-profile";
import type { CardiovascularCode } from "@/lib/cardiovascular-profile";
import { emptyAnswers, answersFromEvidence, profileFromAnswers, type Answers } from "@/lib/prognosis-form";
import { createPrognosisClient, type PrognosisReport, type WorkerState } from "@/lib/prognosis-client";
import { PrognosisForm } from "@/components/prognosis-form";
import { PrognosisResults } from "@/components/prognosis-results";

// Keep uploaded records and user-confirmed inputs in page memory while running Python in a worker.
export default function Home() {
  const [asOf, setAsOf] = useState("");
  const [answers, setAnswers] = useState<Answers>(emptyAnswers);
  const [imported, setImported] = useState<Set<CardiovascularCode>>(new Set());
  const [loaded, setLoaded] = useState(false), [confirmed, setConfirmed] = useState(false);
  const [reading, setReading] = useState(false), [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Choose the assessment date, then a patient record.");
  const [report, setReport] = useState<PrognosisReport | null>(null);
  const [runtime, setRuntime] = useState<WorkerState>({ phase: "loading", message: "Starting prognosis..." });
  const [revision, setRevision] = useState(0), [fileRevision, setFileRevision] = useState(0);
  const client = useRef<ReturnType<typeof createPrognosisClient> | null>(null);
  const generation = useRef(0);

  // Replace failed workers and terminate their Python memory when the component unmounts.
  useEffect(() => {
    let current = true;
    // Ignore callbacks belonging to a worker that has already been replaced.
    function handleState(state: WorkerState) {
      if (current) setRuntime(state);
    }
    try { client.current = createPrognosisClient(handleState); }
    catch { queueMicrotask(() => handleState({ phase: "error", message: "Could not start a browser worker. Retry." })); }
    return () => { current = false; generation.current += 1; client.current?.dispose(); client.current = null; };
  }, [revision]);

  // Drop prior record inputs and results before accepting another assessment.
  function clearRecord() {
    generation.current += 1; setAnswers(emptyAnswers()); setImported(new Set());
    setLoaded(false); setConfirmed(false); setReport(null); setFileRevision(value => value + 1);
  }

  // Changing the assessment date requires a fresh import so earlier evidence is never silently redated.
  function handleDateChange(event: ChangeEvent<HTMLInputElement>) {
    clearRecord(); setAsOf(event.currentTarget.value);
    setMessage("Select a record for this assessment date.");
  }

  // Validate document identity and present evidence before showing any missing-input form.
  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    clearRecord();
    if (!file) { setMessage("No file selected."); return; }
    const request = generation.current;
    setReading(true); setMessage("Reading file...");
    try {
      const format = validatePatientFile(file);
      const text = await file.text();
      const evidence = format === "xml"
        ? readCcdCardiovascularEvidence(text, asOf)
        : readFhirCardiovascularEvidence(JSON.parse(text), asOf);
      const prefilled = answersFromEvidence(evidence, asOf);
      if (request !== generation.current) return;
      setAnswers(prefilled); setImported(new Set(evidence.map(item => item.code)));
      setLoaded(true); setMessage("Record checked. Review its values and complete the missing inputs.");
    } catch (error) {
      if (request === generation.current) setMessage(error instanceof SyntaxError ? "Could not read the file as JSON."
        : error instanceof Error ? error.message : "Could not read the patient record.");
    } finally {
      if (request === generation.current) setReading(false);
    }
  }

  // Any manual change invalidates the earlier confirmation and displayed estimate.
  function handleAnswerChange(code: CardiovascularCode, value: string) {
    setAnswers(current => ({ ...current, [code]: value }));
    setConfirmed(false); setReport(null);
  }

  // Require deliberate review of both imported values and manually completed answers.
  function handleConfirmation(event: ChangeEvent<HTMLInputElement>) {
    setConfirmed(event.currentTarget.checked); setReport(null);
  }

  // Submit only the small validated profile; the raw record never enters the Python worker.
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || reading || !loaded || !confirmed || runtime.phase !== "ready" || !client.current) return;
    const request = generation.current;
    setBusy(true); setReport(null); setMessage("Calculating...");
    try {
      const profile = profileFromAnswers(answers, asOf);
      const result = await client.current.predict(profile);
      if (request !== generation.current) return;
      setReport(result); setMessage("Analysis complete.");
    } catch (error) {
      if (request === generation.current) setMessage(error instanceof Error ? error.message : "Analysis failed.");
    } finally {
      if (request === generation.current) setBusy(false);
    }
  }

  // Start a fresh worker after a failed or timed-out runtime.
  function handleRetry() {
    setReport(null); setBusy(false); setRuntime({ phase: "loading", message: "Starting prognosis..." });
    setRevision(value => value + 1);
  }

  // Clear local record state and replace the worker rather than claiming secure memory erasure.
  function handleClear() {
    clearRecord(); setReading(false); setBusy(false);
    setRuntime({ phase: "loading", message: "Starting prognosis..." }); setRevision(value => value + 1);
    setMessage("Record cleared. Select another record when ready.");
  }

  return <main>
    <h1>Death&apos;s Warrant</h1>
    <p>Cardiovascular research prototype. Lifetime accuracy has not been validated.</p>
    <label htmlFor="assessment-date">Assessment date</label>
    <input id="assessment-date" type="date" value={asOf} onChange={handleDateChange} disabled={reading || busy} required />
    <label htmlFor="patient-file">Patient record — supported FHIR JSON or CCD XML snapshot</label>
    <input key={fileRevision} id="patient-file" type="file" accept=".json,.xml,application/json,application/xml,text/xml"
      onChange={handleFileChange} disabled={!asOf || reading || busy} />
    <p role="status">{message}</p>
    <p role="status">{runtime.message}</p>
    {runtime.phase === "error" && <button type="button" onClick={handleRetry}>Retry model startup</button>}
    {loaded && <form onSubmit={handleSubmit}>
      <PrognosisForm answers={answers} imported={imported} disabled={reading || busy} onChange={handleAnswerChange} />
      <label><input type="checkbox" checked={confirmed} onChange={handleConfirmation} disabled={busy} />
        I have checked that these inputs describe this patient at the selected assessment date.
      </label>
      <button type="submit" disabled={!confirmed || busy || reading || runtime.phase !== "ready"}>Estimate remaining years</button>
    </form>}
    <button type="button" onClick={handleClear}>Clear record</button>
    {report && <PrognosisResults report={report} />}
  </main>;
}
