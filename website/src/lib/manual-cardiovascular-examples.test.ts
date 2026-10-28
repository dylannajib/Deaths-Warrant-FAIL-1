import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { readFhirCardiovascularProfile } from "./cardiovascular-fhir-profile";
import { readCcdCardiovascularProfile } from "./cardiovascular-ccda-profile";
import type { CardiovascularProfile } from "./cardiovascular-profile";

const folder = "../tests/fixtures/cardiovascular/manual/fake/";
const examples = JSON.parse(readFileSync(folder + "expected-results.json", "utf8")) as {
  cases: { id: string; profile: CardiovascularProfile; fhir: string; ccda: string }[];
};

// Keep each manual patient's two record formats consistent with its documented inputs.
it.each(examples.cases)("reads the same synthetic assessment from both formats: $id", example => {
  const fhir = JSON.parse(readFileSync(folder + example.fhir, "utf8"));
  const ccda = readFileSync(folder + example.ccda, "utf8");
  expect(readFhirCardiovascularProfile(fhir, example.profile.asOf)).toEqual(example.profile);
  expect(readCcdCardiovascularProfile(ccda, example.profile.asOf)).toEqual(example.profile);
});
