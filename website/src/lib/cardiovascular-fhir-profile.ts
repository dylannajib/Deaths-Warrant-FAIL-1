import { getSinglePatient, isJsonObject, readBundleResources, validatePatientReferences } from "./fhir";
import { readRecordDate, validateDate } from "./patient-profile";
import { createCardiovascularProfile, readCardiovascularCode, type CardiovascularEvidence, type CardiovascularProfile } from "./cardiovascular-profile";

// Reject unknown structure rather than accepting unimplemented context or modifier semantics.
function objectKeys(value: unknown, allowed: string[], label: string): Record<string, unknown> {
  if (!isJsonObject(value) || Object.keys(value).some(key => !allowed.includes(key))) {
    throw new Error("Unsupported " + label + " fields or context.");
  }
  return value;
}

// Read only the documented, patient-scoped final questionnaire and measurement export subset.
export function readFhirCardiovascularProfile(value: unknown, asOf: string): CardiovascularProfile {
  validateDate(asOf, "Assessment date");
  const bundle = objectKeys(value, ["resourceType", "type", "entry"], "Bundle");
  if (bundle.type !== "collection") throw new Error("Cardiovascular Bundle must be a collection.");
  const resources = readBundleResources(value);
  for (const entry of bundle.entry as unknown[]) objectKeys(entry, ["resource"], "Bundle entry");
  const patient = objectKeys(getSinglePatient(resources), ["resourceType", "id", "birthDate", "gender", "deceasedBoolean"], "Patient");
  if (typeof patient.id !== "string" || !/^[A-Za-z0-9.-]{1,64}$/.test(patient.id)) throw new Error("Invalid patient identity.");
  validatePatientReferences(resources);
  if (patient.deceasedBoolean !== undefined && patient.deceasedBoolean !== false) throw new Error("A living patient is required.");
  if (patient.gender !== undefined && (typeof patient.gender !== "string" || !["male", "female", "other", "unknown"].includes(patient.gender))) {
    throw new Error("Unsupported Patient gender value; recorded sex still requires its own observation.");
  }
  if (patient.birthDate !== undefined) readRecordDate(patient.birthDate, asOf);
  const evidence: CardiovascularEvidence[] = [];
  const observationIds = new Set<string>();
  for (const resource of resources) {
    if (resource === patient) continue;
    objectKeys(resource, ["resourceType", "id", "subject", "status", "code", "effectiveDateTime", "valueInteger", "valueQuantity"], "Observation");
    if (resource.id !== undefined && (typeof resource.id !== "string" || !/^[A-Za-z0-9.-]{1,64}$/.test(resource.id))) throw new Error("Invalid Observation identity.");
    if (typeof resource.id === "string") {
      if (observationIds.has(resource.id)) throw new Error("Duplicate Observation identity.");
      observationIds.add(resource.id);
    }
    if (resource.resourceType !== "Observation" || resource.status !== "final") throw new Error("Only final Observations are supported.");
    objectKeys(resource.subject, ["reference"], "subject");
    const concept = objectKeys(resource.code, ["coding"], "code");
    if (!Array.isArray(concept.coding) || concept.coding.length !== 1) throw new Error("Exactly one cardiovascular coding is required.");
    const coding = objectKeys(concept.coding[0], ["system", "code"], "coding");
    if (typeof coding.system !== "string" || typeof coding.code !== "string") throw new Error("Cardiovascular coding requires string system and code.");
    const code = readCardiovascularCode(coding.system, coding.code);
    const date = readRecordDate(resource.effectiveDateTime, asOf);
    if (resource.valueQuantity !== undefined) {
      if (resource.valueInteger !== undefined || !code.includes("-")) throw new Error("Conflicting or unsupported value types.");
      const quantity = objectKeys(resource.valueQuantity, ["value", "system", "code", "unit"], "quantity");
      if (quantity.system !== "http://unitsofmeasure.org" || typeof quantity.code !== "string" ||
        (quantity.unit !== undefined && quantity.unit !== quantity.code) || typeof quantity.value !== "number") {
        throw new Error("Measurements require an explicit supported UCUM unit and numeric value.");
      }
      evidence.push({ code, date, value: quantity.value, unit: quantity.code });
    } else {
      if (code.includes("-") || typeof resource.valueInteger !== "number") throw new Error("Missing explicit questionnaire integer or measurement quantity.");
      evidence.push({ code, date, value: resource.valueInteger });
    }
  }
  return createCardiovascularProfile(evidence, asOf);
}
