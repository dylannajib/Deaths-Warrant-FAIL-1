import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { readFhirProfile } from "./fhir-profile";
import { validateProfile } from "./patient-profile";

const expected = JSON.parse(readFileSync("../tests/fixtures/prognosis/patient-profile.json", "utf8"));
// Load a fresh FHIR clinical bundle so each test can mutate it independently.
function fixture() {
  return JSON.parse(readFileSync("../tests/fixtures/fhir/heart-failure-profile.json", "utf8"));
}

describe("FHIR clinical extraction", () => {
  it("extracts the shared clinical profile", () => {
    expect(validateProfile(readFhirProfile(fixture(), expected.asOf))).toEqual(expected);
  });
  it("keeps absent history unknown", () => {
    const bundle = fixture();
    bundle.entry.pop();
    expect(readFhirProfile(bundle, expected.asOf).previousStroke).toBeNull();
  });
  it("does not treat refuted or provisional conditions as confirmed history", () => {
    for (const code of ["refuted", "provisional", "entered-in-error"]) {
      const bundle = fixture();
      bundle.entry[1].resource.verificationStatus.coding[0].code = code;
      expect(readFhirProfile(bundle, expected.asOf).heartFailure).toBeNull();
    }
  });
  it("retains confirmed history when a condition is resolved", () => {
    const bundle = fixture();
    bundle.entry[1].resource.clinicalStatus.coding[0].code = "resolved";
    expect(readFhirProfile(bundle, expected.asOf).heartFailure).toBe(true);
  });
  it("ignores incomplete observations and explicit missing answers", () => {
    const bundle = fixture();
    bundle.entry[3].resource.status = "preliminary";
    expect(readFhirProfile(bundle, expected.asOf).previousStroke).toBeNull();
    bundle.entry[3].resource.status = "final";
    bundle.entry[3].resource.dataAbsentReason = { text: "unknown" };
    expect(readFhirProfile(bundle, expected.asOf).previousStroke).toBeNull();
  });
  it("requires explicit history codes for negative answers", () => {
    const bundle = fixture();
    bundle.entry[3].resource.code.coding[0].code = "230690007";
    expect(readFhirProfile(bundle, expected.asOf).previousStroke).toBeNull();
  });
  it.each(["bad-reference", "future-evidence", "bad-birth", "modifier", "deceased", "text-answer", "conflict", "wrong-code-system"])("handles %s safely", problem => {
    const bundle = fixture();
    if (problem === "bad-reference") bundle.entry[1].resource.subject.reference = "Patient/other";
    if (problem === "future-evidence") bundle.entry[2].resource.effectiveDateTime = "2027-01-01";
    if (problem === "bad-birth") bundle.entry[0].resource.birthDate = "1966-02-30";
    if (problem === "modifier") bundle.entry[2].resource.modifierExtension = [{ url: "urn:unsupported" }];
    if (problem === "deceased") bundle.entry[0].resource.deceasedBoolean = true;
    if (problem === "text-answer") bundle.entry[3].resource.valueBoolean = "false";
    if (problem === "wrong-code-system") bundle.entry[3].resource.code.coding[0].system = "urn:unknown";
    if (problem === "conflict") {
      const other = structuredClone(bundle.entry[3]);
      other.resource.valueBoolean = true;
      bundle.entry.push(other);
    }
    expect(() => validateProfile(readFhirProfile(bundle, expected.asOf))).toThrow();
  });
  it("does not recognise a disease from its display label alone", () => {
    const bundle = fixture();
    bundle.entry[1].resource.code = { text: "Heart failure" };
    expect(readFhirProfile(bundle, expected.asOf).heartFailure).toBeNull();
  });
  it("rejects an observation focused on another person", () => {
    const bundle = fixture();
    bundle.entry[2].resource.focus = [{ reference: "RelatedPerson/mother" }];
    expect(() => readFhirProfile(bundle, expected.asOf)).toThrow(/focus/);
  });
  it.each(["onsetPeriod", "onsetAge", "onsetRange", "onsetString"])("rejects unsupported %s instead of bypassing onset checks", field => {
    const bundle = fixture();
    bundle.entry[1].resource[field] = field === "onsetPeriod" ? { start: "2027-01-01" } : "unsupported";
    expect(() => readFhirProfile(bundle, expected.asOf)).toThrow(/onsetDateTime/);
  });
});
