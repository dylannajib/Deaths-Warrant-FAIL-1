import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { readCcdProfile } from "./ccda-profile";
import { readFhirProfile } from "./fhir-profile";
import { validateProfile } from "./patient-profile";

const expected = JSON.parse(readFileSync("../tests/fixtures/prognosis/patient-profile.json", "utf8"));
const xml = readFileSync("../tests/fixtures/ccda/heart-failure-profile.xml", "utf8");

describe("CCD clinical extraction", () => {
  it("agrees with the FHIR adaptor and shared Python profile", () => {
    const fhir = JSON.parse(readFileSync("../tests/fixtures/fhir/heart-failure-profile.json", "utf8"));
    expect(validateProfile(readCcdProfile(xml, expected.asOf))).toEqual(expected);
    expect(readCcdProfile(xml, expected.asOf)).toEqual(readFhirProfile(fhir, expected.asOf));
  });
  it("ignores negated current disease rather than inventing a negative lifetime history", () => {
    const changed = xml.replace('code="275526006"', 'code="230690007"');
    expect(readCcdProfile(changed, expected.asOf).previousStroke).toBeNull();
  });
  it("keeps nullFlavor history unknown", () => {
    const changed = xml.replace('code="275526006"', 'nullFlavor="UNK" code="275526006"');
    expect(readCcdProfile(changed, expected.asOf).previousStroke).toBeNull();
  });
  it("does not read clinical assertions from a family-history section", () => {
    const changed = xml.replace('root="2.16.840.1.113883.10.20.22.2.5.1"', 'root="2.16.840.1.113883.10.20.22.2.15"');
    expect(readCcdProfile(changed, expected.asOf).heartFailure).toBeNull();
  });
  it.each(["future-evidence", "bad-birth", "wrong-namespace", "doctype", "bad-negation", "bad-time"])("rejects %s", problem => {
    let changed = xml;
    if (problem === "future-evidence") changed = xml.replaceAll('value="20260101"', 'value="20270101"');
    if (problem === "bad-birth") changed = xml.replace('value="19660101"', 'value="19660230"');
    if (problem === "wrong-namespace") changed = xml.replace('xmlns="urn:hl7-org:v3"', 'xmlns="urn:wrong"');
    if (problem === "doctype") changed = xml.replace('<ClinicalDocument', '<!DOCTYPE ClinicalDocument [<!ENTITY x "test">]><ClinicalDocument');
    if (problem === "bad-negation") changed = xml.replace('negationInd="true"', 'negationInd="yes"');
    if (problem === "bad-time") changed = xml.replace('value="20260101"', 'value="20260101250000"');
    expect(() => readCcdProfile(changed, expected.asOf)).toThrow();
  });
  it("keeps missing birth dates unknown", () => {
    expect(readCcdProfile(xml.replace('<birthTime value="19660101"/>', ''), expected.asOf).ageYears).toBeNull();
  });
  it("rejects subject overrides and negated enclosing acts", () => {
    expect(() => readCcdProfile(xml.replace('<act classCode="ACT"', '<act negationInd="true" classCode="ACT"'), expected.asOf)).toThrow(/enclosing/);
    const override = '<subject><relatedSubject classCode="PRS"/></subject>';
    expect(() => readCcdProfile(xml.replace('<statusCode code="completed"/>', override + '<statusCode code="completed"/>'), expected.asOf)).toThrow(/subject overrides/);
  });
  it("requires coded values rather than interpreting narrative text", () => {
    expect(readCcdProfile(xml.replaceAll('xsi:type="CD"', 'xsi:type="ST"'), expected.asOf).heartFailure).toBeNull();
  });
  it("rejects section-level subject overrides", () => {
    const changed = xml.replace('<section>', '<section><subject><relatedSubject classCode="PRS"/></subject>');
    expect(() => readCcdProfile(changed, expected.asOf)).toThrow(/subject overrides/);
  });
  it("rejects contradictory assertions", () => {
    const document = new DOMParser().parseFromString(xml, "application/xml");
    const observations = document.getElementsByTagNameNS("urn:hl7-org:v3", "observation");
    const other = observations[2].cloneNode(true) as Element;
    other.setAttribute("negationInd", "false");
    observations[2].parentElement!.appendChild(other);
    expect(() => readCcdProfile(new XMLSerializer().serializeToString(document), expected.asOf)).toThrow(/Conflicting/);
  });
});
