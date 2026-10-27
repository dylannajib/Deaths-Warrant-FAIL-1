import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { readFhirCardiovascularProfile } from "./cardiovascular-fhir-profile";
import { readCcdCardiovascularProfile } from "./cardiovascular-ccda-profile";

const folder = "../tests/fixtures/cardiovascular/";
const expected = JSON.parse(readFileSync(folder + "patient-profile.json", "utf8"));
const fhirText = readFileSync(folder + "fhir.json", "utf8");
const xml = readFileSync(folder + "ccd.xml", "utf8");

// Return isolated mutable FHIR evidence for each rejection test.
function bundle() {
  return JSON.parse(fhirText);
}

// Resolve a fixture observation by exact code to keep mutations independent of entry order.
function observation(value: ReturnType<typeof bundle>, code: string) {
  return value.entry.find((entry: { resource: { code?: { coding: { code: string }[] } } }) => entry.resource.code?.coding[0].code === code).resource;
}

// A single logical Observation cannot supply several independent pieces of evidence.
it("rejects repeated supplied Observation identities", () => {
  const changed = bundle();
  for (const entry of changed.entry) {
    if (entry.resource.resourceType === "Observation") entry.resource.id = "same-observation";
  }
  expect(() => readFhirCardiovascularProfile(changed, expected.asOf)).toThrow(/Duplicate Observation identity/);
});

// Require both formats to reproduce the same shared synthetic profile.
it("extracts exact FHIR/CCD/profile parity", () => {
  expect(readFhirCardiovascularProfile(bundle(), expected.asOf)).toEqual(expected);
  expect(readCcdCardiovascularProfile(xml, expected.asOf)).toEqual(expected);
});

// Exercise format-independent numerical, complete-case and population constraints in both readers.
it.each([
  ["RIDAGEYR", 39, /answer/], ["RIDAGEYR", 80, /answer/], ["RIDAGEYR", 60.5, /integer/],
  ["RIAGENDR", 0, /answer/], ["RIAGENDR", 3, /answer/], ["DIQ010", 3, /answer/],
  ["MCQ160F", 9, /answer/], ["SMQ020", 7, /answer/], ["SMQ040", 9, /answer/],
  ["39156-5", 0, /positive/], ["8480-6", 0, /positive/], ["2160-0", 0, /positive/]
] as const)("rejects invalid %s answer %s in both formats", (code, value, error) => {
  const changed = bundle(), item = observation(changed, code);
  if (item.valueQuantity) item.valueQuantity.value = value;
  else item.valueInteger = value;
  expect(() => readFhirCardiovascularProfile(changed, expected.asOf)).toThrow(error);
  const document = new DOMParser().parseFromString(xml, "application/xml");
  const node = Array.from(document.getElementsByTagName("observation")).find(element => element.getElementsByTagName("code")[0].getAttribute("code") === code)!;
  node.getElementsByTagName("value")[0].setAttribute("value", String(value));
  expect(() => readCcdCardiovascularProfile(new XMLSerializer().serializeToString(document), expected.asOf)).toThrow(error);
});

// No missing question, including sex and either cigarette question, can default to an inferred answer.
it.each(["RIDAGEYR", "RIAGENDR", "MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F", "DIQ010", "SMQ020", "SMQ040", "39156-5", "8480-6", "2160-0"])("requires explicit %s in both formats", code => {
  const changed = bundle();
  changed.entry = changed.entry.filter((entry: { resource: unknown }) => entry.resource !== observation(changed, code));
  expect(() => readFhirCardiovascularProfile(changed, expected.asOf)).toThrow(/Missing explicit/);
  const document = new DOMParser().parseFromString(xml, "application/xml");
  const node = Array.from(document.getElementsByTagName("observation")).find(element => element.getElementsByTagName("code")[0].getAttribute("code") === code)!;
  node.parentElement!.remove();
  expect(() => readCcdCardiovascularProfile(new XMLSerializer().serializeToString(document), expected.asOf)).toThrow(/Missing explicit/);
});

// The cigarette definition needs both lifetime exposure and current daily/some-day smoking.
it.each([[1, 1, true], [1, 2, true], [1, 3, false], [2, 3, false], [2, 1, false]])("uses lifetime %s and current %s for cigarette smoking", (lifetime, current, answer) => {
  const changed = bundle();
  observation(changed, "SMQ020").valueInteger = lifetime;
  observation(changed, "SMQ040").valueInteger = current;
  expect(readFhirCardiovascularProfile(changed, expected.asOf).currentSmoker).toBe(answer);
  const document = new DOMParser().parseFromString(xml, "application/xml");
  for (const [code, answer] of [["SMQ020", lifetime], ["SMQ040", current]]) {
    const node = Array.from(document.getElementsByTagName("observation")).find(element => element.getElementsByTagName("code")[0].getAttribute("code") === code)!;
    node.getElementsByTagName("value")[0].setAttribute("value", String(answer));
  }
  expect(readCcdCardiovascularProfile(new XMLSerializer().serializeToString(document), expected.asOf).currentSmoker).toBe(answer);
});

// Strictly reject unimplemented FHIR status, reference, modifier, value, unit and timing contexts.
it.each([
  ["wrong patient", /reference/], ["subject identifier", /subject/], ["focus", /context/],
  ["modifier", /context/], ["nested modifier", /context/], ["absent", /context/],
  ["preliminary", /final/], ["effective period", /context/], ["stale", /assessment day/],
  ["future", /after/], ["invalid date", /invalid date/], ["unit", /UCUM/], ["unit system", /UCUM/],
  ["quantity comparator", /quantity/], ["multiple values", /Conflicting/], ["multiple coding", /one cardiovascular/],
  ["general tobacco", /Unsupported cardiovascular/], ["infinite", /finite/], ["negative", /positive/],
  ["duplicate", /Duplicate or conflicting/], ["conflict", /Duplicate or conflicting/], ["no CVD", /At least one/],
  ["second patient", /Multiple Patient/], ["birth future", /after/], ["deceased", /living/], ["invalid identity", /identity/],
  ["gender modifier", /gender/], ["id modifier", /identity/]
])("rejects FHIR %s", (problem, error) => {
  const changed = bundle(), item = observation(changed, "2160-0");
  if (problem === "wrong patient") item.subject.reference = "Patient/other";
  if (problem === "subject identifier") item.subject.identifier = { value: "other" };
  if (problem === "focus") item.focus = [{ reference: "Patient/other" }];
  if (problem === "modifier") item.modifierExtension = [];
  if (problem === "nested modifier") item.code.coding[0].modifierExtension = [];
  if (problem === "absent") item.dataAbsentReason = {};
  if (problem === "preliminary") item.status = "preliminary";
  if (problem === "effective period") item.effectivePeriod = { start: expected.asOf };
  if (problem === "stale") item.effectiveDateTime = "2025-12-31";
  if (problem === "future") item.effectiveDateTime = "2026-01-02";
  if (problem === "invalid date") item.effectiveDateTime = "2025-02-30";
  if (problem === "unit") item.valueQuantity.code = "umol/L";
  if (problem === "unit system") item.valueQuantity.system = "urn:untrusted";
  if (problem === "quantity comparator") item.valueQuantity.comparator = "<";
  if (problem === "multiple values") item.valueInteger = 1;
  if (problem === "multiple coding") item.code.coding.push(item.code.coding[0]);
  if (problem === "general tobacco") observation(changed, "SMQ020").code.coding = [{ system: "http://loinc.org", code: "72166-2" }];
  if (problem === "infinite") item.valueQuantity.value = Infinity;
  if (problem === "negative") item.valueQuantity.value = -1;
  if (problem === "duplicate" || problem === "conflict") {
    const other = structuredClone(item);
    if (problem === "conflict") other.valueQuantity.value = 2;
    changed.entry.push({ resource: other });
  }
  if (problem === "no CVD") for (const code of ["MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F"]) observation(changed, code).valueInteger = 2;
  if (problem === "second patient") changed.entry.push(changed.entry[0]);
  if (problem === "birth future") changed.entry[0].resource.birthDate = "2027-01-01";
  if (problem === "deceased") changed.entry[0].resource.deceasedBoolean = true;
  if (problem === "invalid identity") changed.entry[0].resource.id = "invalid/id";
  if (problem === "gender modifier") changed.entry[0].resource.gender = { modifierExtension: [] };
  if (problem === "id modifier") item.id = { modifierExtension: [] };
  expect(() => readFhirCardiovascularProfile(changed, expected.asOf)).toThrow(error);
});

// Attack XML context at every supported ancestor and exercise dates, units and parser protections.
it.each([
  ["DTD", '<ClinicalDocument', '<!DOCTYPE ClinicalDocument [<!ENTITY x "test">]><ClinicalDocument', /document types/],
  ["entity", '<ClinicalDocument', '<!ENTITY x "test"><ClinicalDocument', /entity declarations/],
  ["namespace", 'xmlns="urn:hl7-org:v3"', 'xmlns="urn:wrong"', /CDA Clinical/],
  ["section", 'code="cardiovascular-snapshot"', 'code="family-history"', /section/],
  ["subject", '<observation ', '<observation><subject/></observation><observation ', /context/],
  ["section subject", '<section>', '<section><subject/>', /context/],
  ["body subject", '<structuredBody>', '<structuredBody><subject/>', /context/],
  ["negation", '<observation ', '<observation negationInd="true" ', /negation/],
  ["section negation", '<section>', '<section negationInd="true">', /negation/],
  ["nullFlavor", 'xsi:type="INT" value="2"', 'xsi:type="INT" nullFlavor="UNK" value="2"', /context/],
  ["value type", 'xsi:type="PQ"', 'xsi:type="ST"', /value type/],
  ["unit", 'unit="mg/dL"', 'unit="umol/L"', /UCUM/],
  ["stale", '<effectiveTime value="20260101"/><value xsi:type="PQ"', '<effectiveTime value="20251231"/><value xsi:type="PQ"', /assessment day/],
  ["future", '<effectiveTime value="20260101"/><value xsi:type="PQ"', '<effectiveTime value="20260102"/><value xsi:type="PQ"', /after/],
  ["bad date", 'value="20260101"', 'value="20260230"', /invalid date/],
  ["partial date", 'value="20260101"', 'value="202601"', /YYYYMMDD/],
  ["identity", '<id root="2.25.302768291377756359126047998875640721002" extension="synthetic-cvd"/>', '', /identifier/],
  ["duplicate value", '<value xsi:type="PQ" value="1.1" unit="mg/dL"/>', '<value xsi:type="PQ" value="1.1" unit="mg/dL"/><value xsi:type="PQ" value="2" unit="mg/dL"/>', /exactly one value/]
])("rejects CCD %s", (_problem, before, after, error) => {
  expect(xml).toContain(before);
  expect(() => readCcdCardiovascularProfile(xml.replace(before, after), expected.asOf)).toThrow(error);
});

// Identical and contradictory observations both require reconciliation outside this extractor.
it.each([false, true])("rejects duplicate CCD evidence (conflicting=%s)", conflict => {
  const document = new DOMParser().parseFromString(xml, "application/xml");
  const entry = document.getElementsByTagName("entry")[0];
  const other = entry.cloneNode(true) as Element;
  if (conflict) other.getElementsByTagName("value")[0].setAttribute("value", "61");
  entry.parentElement!.appendChild(other);
  expect(() => readCcdCardiovascularProfile(new XMLSerializer().serializeToString(document), expected.asOf)).toThrow(/Duplicate or conflicting/);
});

// Assessment input must itself be a real complete calendar date.
it.each(["2026-1-1", "2026-02-30", "2026-01-01T00:00:00Z"])("rejects invalid assessment %s", asOf => {
  expect(() => readFhirCardiovascularProfile(bundle(), asOf)).toThrow();
  expect(() => readCcdCardiovascularProfile(xml, asOf)).toThrow();
});
