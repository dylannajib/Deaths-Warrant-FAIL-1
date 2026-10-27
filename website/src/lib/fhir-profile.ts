import { getSinglePatient, isJsonObject, readBundleResources, validatePatientReferences } from "./fhir";
import { addHistory, createProfile, readClinicalCode, readRecordDate, type PatientProfile } from "./patient-profile";

function hasCode(value: unknown, system: string, codes: string[]): boolean {
  return isJsonObject(value) && Array.isArray(value.coding) && value.coding.some(coding =>
    isJsonObject(coding) && coding.system === system && typeof coding.code === "string" && codes.includes(coding.code)
  );
}

function readEvidenceCode(value: unknown) {
  if (!isJsonObject(value) || !Array.isArray(value.coding)) return undefined;
  const recognised = value.coding.flatMap(coding => {
    if (!isJsonObject(coding) || typeof coding.system !== "string" || typeof coding.code !== "string") return [];
    const result = readClinicalCode(coding.system, coding.code);
    return result ? [result] : []
  });
  if (new Set(recognised.map(code => code.field)).size > 1) {
    throw new Error ("Clinical coding identifies conflicting conditions.")
  }
  // For an explicit negative history all recognised codings must identify history.
  if (recognised.length === 0) return undefined;
  return { field: recognised[0].field, historyOnly: recognised.every(code => code.historyOnly) }
}

export function readFhirProfile(value: unknown, asOf: string): PatientProfile {
  const resources = readBundleResources(value);
  validatePatientReferences(resources)
  for (const resource of resources) {
    if (resource.modifierExtension !== undefined) {
      throw new Error ("FHIR modifier extensions are not supported by the clinical reader.")
    }
  }
  const patient = getSinglePatient(resources);
  if (patient.deceasedBoolean !== undefined && typeof patient.deceasedBoolean !== "boolean") {
    throw new Error ("Patient deceased indicator must be a boolean.")
  }
  if (patient.deceasedBoolean === true || patient.deceasedDateTime !== undefined) {
    throw new Error ("Remaining-years estimates require a living patient.")
  }
  const birthDate = patient.birthDate;
  if (birthDate !== undefined && typeof birthDate !== "string") {
    throw new Error ("Patient birth date must be a string.")
  }
  const profile = createProfile(birthDate ?? null, asOf);
  for (const resource of resources) {
    const code = readEvidenceCode(resource.code);
    if (!code) continue;
    if (resource.resourceType === "Condition") {
      if (!hasCode(resource.verificationStatus, "http://terminology.hl7.org/CodeSystem/condition-ver-status", ["confirmed"])) continue;
      if (!hasCode(resource.clinicalStatus, "http://terminology.hl7.org/CodeSystem/condition-clinical", ["active", "recurrence", "relapse", "inactive", "remission", "resolved"])) {
        throw new Error ("A supported confirmed condition needs a recognised clinical status.")
      }
      if (["onsetPeriod", "onsetAge", "onsetRange", "onsetString"].some(field => resource[field] !== undefined)) {
        throw new Error ("Only complete onsetDateTime values are supported for condition onset.")
      }
      if (resource.onsetDateTime !== undefined) readRecordDate(resource.onsetDateTime, asOf);
      readRecordDate(resource.recordedDate ?? resource.onsetDateTime, asOf)
      addHistory(profile, code.field, true)
    } else if (resource.resourceType === "Observation" && code.historyOnly) {
      if (resource.focus !== undefined) {
        throw new Error ("FHIR observation focus contexts are not supported.")
      }
      if (!["final", "amended", "corrected"].includes(String(resource.status))) continue;
      if (resource.dataAbsentReason !== undefined) continue;
      if (typeof resource.valueBoolean !== "boolean") {
        throw new Error ("Supported history observations require an explicit boolean answer.")
      }
      readRecordDate(resource.effectiveDateTime, asOf)
      addHistory(profile, code.field, resource.valueBoolean)
    }
  }
  return profile
}
