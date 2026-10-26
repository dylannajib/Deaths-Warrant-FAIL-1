"use client";

import { useState, type ChangeEvent } from "react";
import { readBundleResources } from "@/lib/fhir";

export default function Home() {
  const [message, setMessage] = useState("No file selected."); const [reading, setReading] = useState(false);
  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) {
      setMessage("No file selected."); return;
    }
    setReading(true); setMessage("Reading file...");
    try {
      const fileText = await file.text(); const value: unknown = JSON.parse(fileText);
      setMessage(readBundleResources(value)
        ? "FHIR Bundle detected. Clinical validation not performed."
        : "This JSON file does not declare a FHIR Bundle.");
    } catch {setMessage("Could not read the file as JSON.");}
    finally {
      setReading(false);
    }
  }
  return(
    <main>
      <h1>Death’s Warrant</h1>
      <p>Read a FHIR patient record locally in your browser.</p>
      <label htmlFor="patient-file">Patient record — FHIR JSON</label>
      <input
        id="patient-file"
        type="file"
        accept=".json,application/json"
        onChange={handleFileChange}
        disabled={reading}
      />
      <p role="status">{message}</p>
    </main>
  );
}
