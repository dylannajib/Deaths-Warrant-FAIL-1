"use client";

import { useState, type ChangeEvent } from "react";
import { validatePatientReferences, readBundleResources } from "@/lib/fhir";
import { parseCdaXml, validateCcdTemplates, getCcdPatientRole, readCcdPatientIdentifiers } from "@/lib/ccda";

export default function Home() {
  const [message, setMessage] = useState("No file selected."); const [reading, setReading] = useState(false);
  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) {
      setMessage("No file selected."); return;
    }
    setReading(true); setMessage("Reading file...");
    try {
      const fileText = await file.text();
      if (file.name.toLowerCase().endsWith(".xml")) {
        const xmlDocument = parseCdaXml(fileText);
        validateCcdTemplates(xmlDocument);
        const patientRole = getCcdPatientRole(xmlDocument);
        readCcdPatientIdentifiers(patientRole);
        setMessage("CCD template declarations recognised. Template versions, patient identity and clinical data not validated.")
      } else if (file.name.toLowerCase().endsWith(".json")) {
        const value: unknown = JSON.parse(fileText);
        const resources = readBundleResources(value);
        validatePatientReferences(resources);
        setMessage(resources.length + " resources read. Supported patient references checked. Clinical data not validated.");
      } else {
        throw new Error ("Select a supported JSON or XML file")
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        setMessage("Could not read the file as JSON.");
      } else if (error instanceof Error) {
        setMessage(error.message)
      } else {
        setMessage("Could not read the file.")
      }
    }
    finally {
      setReading(false);
    }
  }
  return(
    <main>
      <h1>Death&apos;s Warrant</h1>
      <p>Read a FHIR or C-CDA patient record locally in your browser.</p>
      <label htmlFor="patient-file">Patient record — FHIR JSON or C-CDA XML</label>
      <input
        id = "patient-file"
        type ="file"
        accept = ".json, .xml,application/json, application/xml, text/xml"
        onChange = {handleFileChange}
        disabled = {reading}
      />
      <p role="status">{message}</p>
    </main>
  );
}
