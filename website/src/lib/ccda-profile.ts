import { getCdaChildren, getCcdPatientRole, parseCdaXml, readCcdPatientIdentifiers, validateCcdTemplates } from "./ccda";
import { addHistory, createProfile, readClinicalCode, readRecordDate, type PatientProfile } from "./patient-profile";

// Check direct CDA template declarations against the supported identifier roots.
function hasTemplate(element: Element, roots: string[]): boolean {
    return getCdaChildren(element, "templateId").some(template => roots.includes(template.getAttribute("root") ?? ""))
}

// Validate a complete CDA timestamp and reject evidence dated after assessment.
function readCdaDate(element: Element | undefined, asOf: string): string {
    const value = element?.getAttribute("value");
    if (!value || !/^\d{8}(\d{6}([+-]\d{4})?)?$/.test(value)) {
        throw new Error ("CCD clinical dates must contain a complete supported date.")
    }
    if (value.length > 8) {
        const hour = Number(value.slice(8, 10)), minute = Number(value.slice(10, 12)), second = Number(value.slice(12, 14));
        if (hour > 23 || minute > 59 || second > 59) throw new Error ("CCD contains an invalid time.");
        if (value.length > 14 && (Number(value.slice(15, 17)) > 23 || Number(value.slice(17, 19)) > 59)) {
            throw new Error ("CCD contains an invalid timezone.")
        }
    }
    return readRecordDate(value.slice(0, 4) + "-" + value.slice(4, 6) + "-" + value.slice(6, 8), asOf)
}

// Extract age and supported coded histories from completed CCD problem observations.
export function readCcdProfile(xmlText: string, asOf: string): PatientProfile {
    const document = parseCdaXml(xmlText);
    validateCcdTemplates(document)
    const role = getCcdPatientRole(document);
    readCcdPatientIdentifiers(role)
    const patient = getCdaChildren(role, "patient")[0];
    if (Array.from(patient.children).some(element =>
        ["urn:hl7-org:v3", "urn:hl7-org:sdtc"].includes(element.namespaceURI ?? "") &&
        ((element.localName === "deceasedInd" && element.getAttribute("value") === "true") || element.localName === "deceasedTime")
    )) throw new Error ("Remaining-years estimates require a living patient.");
    const birthTimes = getCdaChildren(patient, "birthTime");
    if (birthTimes.length > 1) throw new Error ("CCD must not contain multiple birth dates.");
    const birthDate = birthTimes.length === 1 && !birthTimes[0].hasAttribute("nullFlavor") ? readCdaDate(birthTimes[0], asOf) : null;
    const profile = createProfile(birthDate, asOf);
    const bodies = getCdaChildren(document.documentElement, "component").flatMap(component => getCdaChildren(component, "structuredBody"));
    const sections = bodies.flatMap(body => getCdaChildren(body, "component")).flatMap(component => getCdaChildren(component, "section"));
    for (const section of sections) {
        if (!hasTemplate(section, ["2.16.840.1.113883.10.20.22.2.5", "2.16.840.1.113883.10.20.22.2.5.1"])) continue;
        if (section.hasAttribute("nullFlavor")) continue;
        const observations = Array.from(section.getElementsByTagNameNS("urn:hl7-org:v3", "observation"));
        for (const observation of observations) {
            if (!hasTemplate(observation, ["2.16.840.1.113883.10.20.22.4.4"])) continue;
            // Subject overrides and negated enclosing acts need interpretation we do not implement.
            let context: Element | null = observation;
            while (context) {
                if (getCdaChildren(context, "subject").length > 0 || getCdaChildren(context, "participant").some(participant => participant.getAttribute("typeCode") === "SBJ")) {
                    throw new Error ("CCD clinical subject overrides are not supported.")
                }
                if (context !== observation && context.hasAttribute("negationInd") && context.getAttribute("negationInd") !== "false") {
                    throw new Error ("CCD negated enclosing acts are not supported.")
                }
                if (context !== observation && context.hasAttribute("nullFlavor")) {
                    throw new Error ("CCD clinical context is unknown.")
                }
                if (context === section) break;
                context = context.parentElement;
            }
            if (observation.getAttribute("classCode") !== "OBS" || observation.getAttribute("moodCode") !== "EVN") continue;
            if (observation.hasAttribute("nullFlavor")) continue;
            if (getCdaChildren(observation, "statusCode")[0]?.getAttribute("code") !== "completed") continue;
            const negation = observation.getAttribute("negationInd");
            if (negation !== null && negation !== "true" && negation !== "false") throw new Error ("CCD contains an invalid negation indicator.");
            const assertion = getCdaChildren(observation, "code")[0];
            if (assertion?.getAttribute("code") !== "ASSERTION" || assertion.getAttribute("codeSystem") !== "2.16.840.1.113883.5.4") continue;
            const values = getCdaChildren(observation, "value");
            if (values.length !== 1 || values[0].hasAttribute("nullFlavor")) continue;
            const value = values[0];
            if (value.getAttributeNS("http://www.w3.org/2001/XMLSchema-instance", "type") !== "CD") continue;
            const code = readClinicalCode(value.getAttribute("codeSystem") ?? "", value.getAttribute("code") ?? "");
            if (!code || (negation === "true" && !code.historyOnly)) continue;
            const effectiveTime = getCdaChildren(observation, "effectiveTime")[0];
            readCdaDate(effectiveTime?.hasAttribute("value") ? effectiveTime : effectiveTime && getCdaChildren(effectiveTime, "low")[0], asOf);
            addHistory(profile, code.field, negation !== "true")
        }
    }
    return profile
}
