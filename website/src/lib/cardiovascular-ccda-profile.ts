import { getCdaChildren, getCcdPatientRole, parseCdaXml, readCcdPatientIdentifiers, validateCcdTemplates } from "./ccda";
import { readRecordDate, validateDate } from "./patient-profile";
import { cardiovascularQuestionOid, createCardiovascularProfile, readCardiovascularCode, type CardiovascularEvidence, type CardiovascularProfile } from "./cardiovascular-profile";

const cda = "urn:hl7-org:v3", xsi = "http://www.w3.org/2001/XMLSchema-instance";
const structure: Record<string, { children: string[]; attributes: string[] }> = {
  ClinicalDocument: { children: ["templateId", "id", "code", "title", "effectiveTime", "recordTarget", "component"], attributes: [] },
  templateId: { children: [], attributes: ["root", "extension"] },
  id: { children: [], attributes: ["root", "extension"] },
  code: { children: [], attributes: ["code", "codeSystem"] },
  title: { children: [], attributes: [] },
  effectiveTime: { children: [], attributes: ["value"] },
  recordTarget: { children: ["patientRole"], attributes: [] },
  patientRole: { children: ["id", "patient"], attributes: [] },
  patient: { children: ["birthTime", "administrativeGenderCode"], attributes: [] },
  birthTime: { children: [], attributes: ["value"] },
  administrativeGenderCode: { children: [], attributes: ["code", "codeSystem"] },
  component: { children: ["structuredBody", "section"], attributes: [] },
  structuredBody: { children: ["component"], attributes: [] },
  section: { children: ["code", "entry"], attributes: [] },
  entry: { children: ["observation"], attributes: [] },
  observation: { children: ["code", "statusCode", "effectiveTime", "value"], attributes: ["classCode", "moodCode"] },
  statusCode: { children: [], attributes: ["code"] },
  value: { children: [], attributes: ["value", "unit"] }
};

// Enforce an intentionally narrow tree so nested subjects, negation and section overrides cannot be ignored.
function validateStructure(document: Document): void {
  for (const element of Array.from(document.getElementsByTagName("*"))) {
    const rule = structure[element.localName];
    if (element.namespaceURI !== cda || !rule || Array.from(element.children).some(child => !rule.children.includes(child.localName))) {
      throw new Error("Unsupported CCD structure or clinical context.");
    }
    for (const attribute of Array.from(element.attributes)) {
      if (attribute.namespaceURI === "http://www.w3.org/2000/xmlns/") continue;
      if (element.localName === "value" && attribute.namespaceURI === xsi && attribute.localName === "type") continue;
      if (attribute.namespaceURI !== null || !rule.attributes.includes(attribute.name)) throw new Error("Unsupported CCD attribute, negation or context.");
    }
  }
}

// Require one direct child, rejecting duplicate values and ambiguous wrapper structure.
function single(parent: Element, name: string): Element {
  const children = getCdaChildren(parent, name);
  if (children.length !== 1) throw new Error("CCD requires exactly one " + name + ".");
  return children[0];
}

// Accept complete calendar dates only; timestamps and intervals need additional interpretation.
function date(element: Element, asOf: string): string {
  const value = element.getAttribute("value") ?? "";
  if (!/^\d{8}$/.test(value)) throw new Error("CCD dates must be complete YYYYMMDD dates.");
  return readRecordDate(value.slice(0, 4) + "-" + value.slice(4, 6) + "-" + value.slice(6, 8), asOf);
}

// Extract the strict questionnaire snapshot section from a single-patient CCD export.
export function readCcdCardiovascularProfile(xmlText: string, asOf: string): CardiovascularProfile {
  validateDate(asOf, "Assessment date");
  const document = parseCdaXml(xmlText);
  validateCcdTemplates(document);
  validateStructure(document);
  const root = document.documentElement;
  const role = getCcdPatientRole(document);
  readCcdPatientIdentifiers(role);
  const patient = single(role, "patient");
  if (getCdaChildren(patient, "birthTime").length > 1 || getCdaChildren(patient, "administrativeGenderCode").length > 1) {
    throw new Error("Duplicate CCD patient demographics.");
  }
  for (const birth of getCdaChildren(patient, "birthTime")) date(birth, asOf);
  if (date(single(root, "effectiveTime"), asOf) !== asOf) throw new Error("CCD document must be dated on the assessment day.");
  const body = single(single(root, "component"), "structuredBody");
  if (getCdaChildren(root, "component")[0].children.length !== 1) throw new Error("Unsupported CCD body context.");
  const sectionComponent = single(body, "component");
  const section = single(sectionComponent, "section");
  if (sectionComponent.children.length !== 1) throw new Error("Unsupported CCD section context.");
  const sectionCode = single(section, "code");
  if (sectionCode.getAttribute("code") !== "cardiovascular-snapshot" || sectionCode.getAttribute("codeSystem") !== cardiovascularQuestionOid) {
    throw new Error("Unsupported CCD cardiovascular section.");
  }
  const evidence: CardiovascularEvidence[] = [];
  for (const entry of getCdaChildren(section, "entry")) {
    const observation = single(entry, "observation");
    if (observation.getAttribute("classCode") !== "OBS" || observation.getAttribute("moodCode") !== "EVN" ||
      single(observation, "statusCode").getAttribute("code") !== "completed") throw new Error("CCD requires completed event observations.");
    const coding = single(observation, "code");
    const code = readCardiovascularCode(coding.getAttribute("codeSystem") ?? "", coding.getAttribute("code") ?? "");
    const value = single(observation, "value");
    const measurement = code.includes("-");
    if (value.getAttributeNS(xsi, "type") !== (measurement ? "PQ" : "INT")) throw new Error("Unsupported CCD value type.");
    const raw = value.getAttribute("value") ?? "";
    if (!/^(0|[1-9]\d*)(\.\d+)?$/.test(raw)) throw new Error("CCD values must be explicit numeric answers.");
    const unit = value.getAttribute("unit") ?? undefined;
    evidence.push({ code, value: Number(raw), unit, date: date(single(observation, "effectiveTime"), asOf) });
  }
  return createCardiovascularProfile(evidence, asOf);
}
