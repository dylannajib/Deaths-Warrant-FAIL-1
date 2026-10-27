export type PatientProfile = {
  asOf: string; ageYears: number | null;
  heartFailure: boolean | null;
  previousHeartAttack: boolean | null; previousStroke: boolean | null;
};

export type PrognosisInput = PatientProfile & {
  ageYears: number;
  heartFailure: true;
  previousHeartAttack: boolean;
  previousStroke: boolean;
};

export type HistoryField = "heartFailure" | "previousHeartAttack" | "previousStroke";

// Explicit supported codes, not a SNOMED hierarchy or a general terminology service.
const clinicalCodes: Record<string, { field: HistoryField; historyOnly: boolean }> = {
  "84114007": { field: "heartFailure", historyOnly: false },
  "42343007": { field: "heartFailure", historyOnly: false },
  "22298006": { field: "previousHeartAttack", historyOnly: false },
  "1755008": { field: "previousHeartAttack", historyOnly: false },
  "399211009": { field: "previousHeartAttack", historyOnly: true },
  "230690007": { field: "previousStroke", historyOnly: false },
  "275526006": { field: "previousStroke", historyOnly: true }
};

export function readClinicalCode(system: string, code: string) {
  if (system !== "http://snomed.info/sct" && system !== "2.16.840.1.113883.6.96") {
    return undefined
  }
  return Object.hasOwn(clinicalCodes, code) ? clinicalCodes[code] : undefined
}

export function validateDate(value: string, label: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error (label + " must contain a complete YYYY-MM-DD date.")
  }
  const date = new Date(value + "T00:00:00Z");
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new Error (label + " contains an invalid date.")
  }
  return value
}

export function readRecordDate(value: unknown, asOf: string): string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}(T([01]\d|2[0-3]):[0-5]\d:[0-5]\d(\.\d+)?(Z|[+-]([01]\d|2[0-3]):[0-5]\d))?$/.test(value)) {
    throw new Error ("Clinical evidence needs a complete date or supported date-time.")
  }
  if (value.length > 10 && !Number.isFinite(Date.parse(value))) {
    throw new Error ("Clinical evidence contains an invalid date-time.")
  }
  const date = validateDate(value.slice(0, 10), "Clinical evidence");
  if (date > asOf) {
    throw new Error ("Clinical evidence is dated after the assessment date.")
  }
  return date
}

export function createProfile(birthDate: string | null, asOf: string): PatientProfile {
  validateDate(asOf, "Assessment date")
  let ageYears: number | null = null;
  if (birthDate !== null) {
    validateDate(birthDate, "Birth date")
    if (birthDate > asOf) {
      throw new Error ("Birth date cannot be after the assessment date.")
    }
    ageYears = Number(asOf.slice(0, 4)) - Number(birthDate.slice(0, 4));
    if (asOf.slice(5) < birthDate.slice(5)) ageYears -= 1;
  }
  return { asOf, ageYears, heartFailure: null, previousHeartAttack: null, previousStroke: null }
}

export function addHistory(profile: PatientProfile, field: HistoryField, value: boolean): void {
  if (profile[field] !== null && profile[field] !== value) {
    throw new Error ("Conflicting clinical history for " + field + ".")
  }
  profile[field] = value;
}

export function validateProfile(profile: PatientProfile): PrognosisInput {
  validateDate(profile.asOf, "Assessment date")
  if (profile.ageYears === null || !Number.isInteger(profile.ageYears) || profile.ageYears < 40 || profile.ageYears > 79) {
    throw new Error ("The research model requires a known age from 40 to 79 years.")
  }
  if (profile.heartFailure !== true) {
    throw new Error ("The research model requires documented heart-failure history.")
  }
  if (typeof profile.previousHeartAttack !== "boolean" || typeof profile.previousStroke !== "boolean") {
    throw new Error ("Explicit previous heart-attack and stroke histories are required; missing records do not mean no.")
  }
  return { ...profile, ageYears: profile.ageYears, heartFailure: true,
    previousHeartAttack: profile.previousHeartAttack, previousStroke: profile.previousStroke };
}
