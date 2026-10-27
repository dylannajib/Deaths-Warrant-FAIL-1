import { cardiovascularCodes, createCardiovascularProfile, validateCardiovascularEvidence, type CardiovascularCode, type CardiovascularEvidence } from "./cardiovascular-profile";

type Field = { code: CardiovascularCode; label: string; unit?: string; choices?: readonly (readonly [string, string])[] };
const yesNo = [["1", "Yes"], ["2", "No"]] as const;
export const prognosisFields: Field[] = [
  { code: "RIDAGEYR", label: "Completed age in years" },
  { code: "RIAGENDR", label: "Recorded demographic sex", choices: [["1", "Male"], ["2", "Female"]] },
  { code: "MCQ160B", label: "Ever told you had congestive heart failure?", choices: yesNo },
  { code: "MCQ160C", label: "Ever told you had coronary heart disease?", choices: yesNo },
  { code: "MCQ160D", label: "Ever told you had angina?", choices: yesNo },
  { code: "MCQ160E", label: "Ever told you had a heart attack?", choices: yesNo },
  { code: "MCQ160F", label: "Ever told you had a stroke?", choices: yesNo },
  { code: "DIQ010", label: "Ever told you had diabetes? Leave unknown if borderline or uncertain.", choices: yesNo },
  { code: "SMQ020", label: "Smoked at least 100 cigarettes in your lifetime?", choices: yesNo },
  { code: "SMQ040", label: "Do you now smoke cigarettes?", choices: [["1", "Every day"], ["2", "Some days"], ["3", "Not at all"]] },
  { code: "39156-5", label: "BMI", unit: "kg/m2" },
  { code: "8480-6", label: "Mean systolic blood pressure at this assessment", unit: "mm[Hg]" },
  { code: "2160-0", label: "Serum creatinine", unit: "mg/dL" }
];
export type Answers = Record<CardiovascularCode, string>;

// Start every answer as unknown instead of supplying negative medical histories.
export function emptyAnswers(): Answers {
  return Object.fromEntries(Object.keys(cardiovascularCodes).map(code => [code, ""])) as Answers;
}

// Validate present evidence and prefill only values explicitly supplied by the record.
export function answersFromEvidence(evidence: CardiovascularEvidence[], asOf: string): Answers {
  validateCardiovascularEvidence(evidence, asOf);
  const answers = emptyAnswers();
  for (const item of evidence) answers[item.code] = String(item.value);
  return answers;
}

// Require complete valid answers before producing the exact Python model input.
export function profileFromAnswers(answers: Answers, asOf: string) {
  const evidence: CardiovascularEvidence[] = [];
  for (const field of prognosisFields) {
    if (answers[field.code].trim() === "") throw new Error("Complete or confirm: " + field.label);
    evidence.push({ code: field.code, value: Number(answers[field.code]), date: asOf, unit: field.unit });
  }
  return createCardiovascularProfile(evidence, asOf);
}
