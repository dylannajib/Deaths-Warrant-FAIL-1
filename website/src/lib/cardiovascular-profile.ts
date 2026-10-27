import { readRecordDate, validateDate } from "./patient-profile";

export type CardiovascularProfile = {
  asOf: string; ageYears: number; recordedSex: 1 | 2;
  heartFailure: boolean; coronaryHeartDisease: boolean; angina: boolean;
  previousHeartAttack: boolean; previousStroke: boolean; diabetes: boolean; currentSmoker: boolean;
  bmi: number; systolicBloodPressure: number; creatinine: number;
};

export const cardiovascularQuestionSystem = "urn:deaths-warrant:nhanes-questionnaire:v1";
export const cardiovascularQuestionOid = "2.25.302768291377756359126047998875640721001";
export const cardiovascularCodes = {
  RIDAGEYR: "ageYears", RIAGENDR: "recordedSex", MCQ160B: "heartFailure",
  MCQ160C: "coronaryHeartDisease", MCQ160D: "angina", MCQ160E: "previousHeartAttack",
  MCQ160F: "previousStroke", DIQ010: "diabetes", SMQ020: "lifetimeCigarettes", SMQ040: "smokingNow",
  "39156-5": "bmi", "8480-6": "systolicBloodPressure", "2160-0": "creatinine"
} as const;
export type CardiovascularCode = keyof typeof cardiovascularCodes;
export type CardiovascularEvidence = { code: CardiovascularCode; value: number; date: string; unit?: string };

// Accept only the documented exact question and LOINC codes, without terminology inference.
export function readCardiovascularCode(system: string, code: string): CardiovascularCode {
  const question = system === cardiovascularQuestionSystem || system === cardiovascularQuestionOid;
  const loinc = system === "http://loinc.org" || system === "2.16.840.1.113883.6.1";
  if (!Object.hasOwn(cardiovascularCodes, code) || (code.includes("-") ? !loinc : !question)) {
    throw new Error("Unsupported cardiovascular code or code system.");
  }
  return code as CardiovascularCode;
}

// Build one complete exam snapshot; identical duplicates also require unsupported reconciliation.
export function createCardiovascularProfile(evidence: CardiovascularEvidence[], asOf: string): CardiovascularProfile {
  validateDate(asOf, "Assessment date");
  const values: Partial<Record<CardiovascularCode, number>> = {};
  for (const item of evidence) {
    if (!Object.hasOwn(cardiovascularCodes, item.code)) throw new Error("Unsupported cardiovascular evidence code.");
    if (readRecordDate(item.date, asOf) !== asOf) throw new Error("Evidence must be dated on the assessment day.");
    if (Object.hasOwn(values, item.code)) throw new Error("Duplicate or conflicting cardiovascular evidence: " + item.code);
    if (!Number.isFinite(item.value)) throw new Error("Cardiovascular values must be finite.");
    const unit = ({ "39156-5": "kg/m2", "8480-6": "mm[Hg]", "2160-0": "mg/dL" } as Record<string, string>)[item.code];
    if (unit) {
      if (item.unit !== unit) throw new Error("Unsupported UCUM unit for " + item.code + "; expected " + unit);
      if (item.value <= 0) throw new Error("Measurements must be positive.");
    } else {
      if (item.unit !== undefined || !Number.isInteger(item.value)) throw new Error("Questionnaire values must be unitless integers.");
      const valid = item.code === "RIDAGEYR" ? item.value >= 40 && item.value <= 79
        : item.code === "SMQ040" ? [1, 2, 3].includes(item.value) : [1, 2].includes(item.value);
      if (!valid) throw new Error("Unsupported or unknown questionnaire answer for " + item.code);
    }
    values[item.code] = item.value;
  }
  for (const code of Object.keys(cardiovascularCodes)) {
    if (!Object.hasOwn(values, code)) throw new Error("Missing explicit cardiovascular evidence: " + code);
  }
  const v = values as Record<CardiovascularCode, number>;
  if (![v.MCQ160B, v.MCQ160C, v.MCQ160D, v.MCQ160E, v.MCQ160F].includes(1)) {
    throw new Error("At least one of the five cardiovascular histories must be true.");
  }
  return { asOf, ageYears: v.RIDAGEYR, recordedSex: v.RIAGENDR as 1 | 2,
    heartFailure: v.MCQ160B === 1, coronaryHeartDisease: v.MCQ160C === 1, angina: v.MCQ160D === 1,
    previousHeartAttack: v.MCQ160E === 1, previousStroke: v.MCQ160F === 1, diabetes: v.DIQ010 === 1,
    currentSmoker: v.SMQ020 === 1 && [1, 2].includes(v.SMQ040),
    bmi: v["39156-5"], systolicBloodPressure: v["8480-6"], creatinine: v["2160-0"] };
}
