import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { readFhirCardiovascularEvidence, readFhirCardiovascularProfile } from "./cardiovascular-fhir-profile";
import { readCcdCardiovascularEvidence } from "./cardiovascular-ccda-profile";
import { answersFromEvidence, emptyAnswers, profileFromAnswers } from "./prognosis-form";

const folder = "../tests/fixtures/cardiovascular/";
const fixture = JSON.parse(readFileSync(folder + "fhir.json", "utf8"));
const expected = JSON.parse(readFileSync(folder + "patient-profile.json", "utf8"));

// Preserve every explicit value through import, form confirmation and model-input conversion.
it("round-trips the complete synthetic assessment", () => {
  const evidence = readFhirCardiovascularEvidence(fixture, expected.asOf);
  expect(profileFromAnswers(answersFromEvidence(evidence, expected.asOf), expected.asOf)).toEqual(expected);
});

// Return absent fields as blank answers while the original full-profile API remains strict.
it("allows missing evidence without treating it as a negative answer", () => {
  const partial = structuredClone(fixture);
  partial.entry = partial.entry.filter((entry: { resource: { code?: { coding: { code: string }[] } } }) =>
    entry.resource.code?.coding[0].code !== "MCQ160B");
  const answers = answersFromEvidence(readFhirCardiovascularEvidence(partial, expected.asOf), expected.asOf);
  expect(answers.MCQ160B).toBe("");
  expect(() => readFhirCardiovascularProfile(partial, expected.asOf)).toThrow(/Missing/);
  expect(() => profileFromAnswers(answers, expected.asOf)).toThrow(/Complete or confirm/);
  answers.MCQ160B = "1";
  expect(profileFromAnswers(answers, expected.asOf)).toEqual(expected);
});

// Permit a structurally valid CCD snapshot to request a missing measurement.
it("retains missing CCD measurements as unknown", () => {
  const document = new DOMParser().parseFromString(readFileSync(folder + "ccd.xml", "utf8"), "application/xml");
  const observation = Array.from(document.getElementsByTagName("observation")).find(element =>
    element.getElementsByTagName("code")[0].getAttribute("code") === "2160-0")!;
  observation.parentElement!.remove();
  const evidence = readCcdCardiovascularEvidence(new XMLSerializer().serializeToString(document), expected.asOf);
  expect(answersFromEvidence(evidence, expected.asOf)["2160-0"]).toBe("");
});

// Missing-input support must never swallow an invalid unit or identity failure.
it("still rejects invalid present evidence", () => {
  const invalid = structuredClone(fixture);
  const observation = invalid.entry.find((entry: { resource: { code?: { coding: { code: string }[] } } }) =>
    entry.resource.code?.coding[0].code === "2160-0").resource;
  observation.valueQuantity.code = "umol/L";
  expect(() => readFhirCardiovascularEvidence(invalid, expected.asOf)).toThrow(/unit/);
  observation.subject.reference = "Patient/somebody-else";
  expect(() => readFhirCardiovascularEvidence(invalid, expected.asOf)).toThrow(/reference/);
});

// Unknown initial answers and non-finite typed values cannot reach the worker.
it("rejects incomplete or non-finite manual inputs", () => {
  expect(Object.values(emptyAnswers()).every(value => value === "")).toBe(true);
  const answers = answersFromEvidence(readFhirCardiovascularEvidence(fixture, expected.asOf), expected.asOf);
  answers["2160-0"] = "Infinity";
  expect(() => profileFromAnswers(answers, expected.asOf)).toThrow(/finite/);
});
