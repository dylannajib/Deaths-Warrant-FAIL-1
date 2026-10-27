// Narrow unknown JSON values to non-null objects while excluding arrays.
export function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Recognise a JSON object that declares the FHIR Bundle resource type.
export function isFhirBundle(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    "resourceType" in value &&
    value.resourceType === "Bundle"
  );
}

// Require a FHIR Bundle and collect entries with nonblank resource types.
export function readBundleResources(value: unknown): Record<string, unknown> [] {
  if (!isJsonObject(value)) {
    throw new Error("File must contain a JSON object.")
  }
  if (!isFhirBundle(value)) {
    throw new Error ("File must contain a FHIR bundle.")
  }
  if (!Array.isArray(value.entry)) {
    throw new Error ("Bundle entry property must be an array.")
  }
  
  const resources: Record<string, unknown>[] = [];
  
  for (const entry of value.entry) {
    if (!isJsonObject(entry)) {
      throw new Error ("Each Bundle entry must be a JSON object.")
    }
    if (!isJsonObject(entry.resource)) {
      throw new Error ("Each Bundle entry must contain a JSON object.")
    }
    if (typeof entry.resource.resourceType !== "string") {
      throw new Error ("Each resource must have a string resourceType.")
    }
    if (entry.resource.resourceType.trim() === "") {
      throw new Error ("Resource type cannot be blank.")
    }
    resources.push(entry.resource)
  }
  return (resources)
}

// Require exactly one Patient resource and return it for identity checks.
export function getSinglePatient(resources: Record<string, unknown>[]): Record<string, unknown> {
  const patients = resources.filter(
    resource => resource.resourceType === "Patient"
  );
  if (patients.length === 0) {
    throw new Error ("Bundle must contain one Patient resource")
  }
  if (patients.length > 1) {
    throw new Error ("Multiple Patient resources are not supported")
  }
  return patients[0]
}

// Build the local Patient/id reference from a nonblank patient resource ID.
function getPatientReference(patient: Record<string, unknown>): string {
  if (typeof patient.id !== "string") {
    throw new Error ("Patient ID resource must have a non-blank string.")
  }
  if (patient.id.trim() === "") {
    throw new Error ("Patient ID resource cannot be blank.")
  }
  return ("Patient/" + patient.id)
}

// Require supported clinical resources to reference the bundle's single patient.
export function validatePatientReferences(
  resources: Record<string, unknown>[]
): void {
  const patient = getSinglePatient(resources);
  const patientReference = getPatientReference(patient);
  for (const resource of resources) {
    if (resource.resourceType === "Patient") {
      continue
    } if (resource.resourceType !== "Condition" && resource.resourceType !== "Observation") {
      throw new Error ("Only Patient, Condition and Observation resources are currently supported.")
    } if (!isJsonObject(resource.subject)) {
      throw new Error ("Each clinical resource must contain a subject object.")
    } if (resource.subject.reference !== patientReference) {
      throw new Error ("Clinical resource must reference the Bundle patient using Patient/id.")
    }
  }
}
