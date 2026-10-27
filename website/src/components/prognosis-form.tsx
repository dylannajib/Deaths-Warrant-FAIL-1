import type { ChangeEvent } from "react";
import { prognosisFields, type Answers } from "@/lib/prognosis-form";
import type { CardiovascularCode } from "@/lib/cardiovascular-profile";

type Props = {
  answers: Answers; imported: Set<CardiovascularCode>; disabled: boolean;
  onChange: (code: CardiovascularCode, value: string) => void;
};

// Display the exact model questions with explicit unknown choices and visible source labels.
export function PrognosisForm({ answers, imported, disabled, onChange }: Props) {
  return <fieldset disabled={disabled}>
    <legend>Review the assessment and complete missing inputs</legend>
    <p>Use values for the selected assessment date. Leave unknown answers blank; do not guess.</p>
    <p>Recorded sex means the demographic variable used in the source data; it is not inferred from gender identity.</p>
    {prognosisFields.map(field => {
      // Update this field and let the parent clear any result based on older answers.
      function handleChange(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
        onChange(field.code, event.currentTarget.value);
      }
      return <div key={field.code}>
        <label htmlFor={field.code}>{field.label}{field.unit ? " (" + field.unit + ")" : ""}</label>
        {field.choices
          ? <select id={field.code} value={answers[field.code]} disabled={imported.has(field.code)} onChange={handleChange} required>
              <option value="">Unknown / not supplied</option>
              {field.choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          : <input id={field.code} type="number" value={answers[field.code]} disabled={imported.has(field.code)}
              step={field.code === "RIDAGEYR" ? "1" : "any"} min={field.code === "RIDAGEYR" ? 40 : undefined}
              max={field.code === "RIDAGEYR" ? 79 : undefined} onChange={handleChange} required />}
        <small>{imported.has(field.code) ? "From the uploaded record" : "Needs your answer"}</small>
      </div>;
    })}
  </fieldset>;
}
