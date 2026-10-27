type CcdPatientIdentifier = {
    root: string; extension?: string;
};

export function parseCdaXml(xmlText: string): Document {
    if (/<!DOCTYPE|<!ENTITY/i.test(xmlText)) {
        throw new Error("XML document types and entity declarations are not supported.")
    }
    const parser = new DOMParser();
    const xmlDocument = parser.parseFromString(xmlText, "application/xml");
    if (xmlDocument.getElementsByTagNameNS("*", "parsererror").length > 0) {
        throw new Error ("File contains malformed XML.")
    }

    const root = xmlDocument.documentElement;
    if (root.localName !== "ClinicalDocument" || root.namespaceURI !== "urn:hl7-org:v3") {
        throw new Error ("XML file did not declare a CDA Clinical Document.")
    } 

    return xmlDocument
}

function hasCdaTemplate(xmlDocument: Document, templateRoot: string): boolean {
    return Array.from(xmlDocument.documentElement.children).some(element =>
        element.namespaceURI === "urn:hl7-org:v3" &&
        element.localName === "templateId" &&
        element.getAttribute("root") === templateRoot
    );
}

export function validateCcdTemplates(xmlDocument: Document): void{
    if (!hasCdaTemplate(xmlDocument, "2.16.840.1.113883.10.20.22.1.1")) {
        throw new Error ("Document must declare a supported US Realm Header tempalte.")
    } if (!hasCdaTemplate(xmlDocument, "2.16.840.1.113883.10.20.22.1.2")) {
        throw new Error ("Only documents declaring the C-CDA template are currently supported.")
    }
}

export function getCdaChildren(parent: Element, name: string): Element[] {
    return Array.from(parent.children).filter(element =>
        element.namespaceURI === "urn:hl7-org:v3" &&
        element.localName === name
    );
}

export function getCcdPatientRole(xmlDocument: Document): Element {
    const recordTargets = getCdaChildren(xmlDocument.documentElement, "recordTarget")
    if (recordTargets.length !== 1) {
        throw new Error ("CCD must contain exactly one recordTarget.")
    }

    const patientRoles = getCdaChildren(recordTargets[0], "patientRole")
    if (patientRoles.length !== 1) {
        throw new Error ("CCD recordTarget must contain exactly one patientRole.")
    }

    const patients = getCdaChildren(patientRoles[0], "patient")
    if (patients.length !== 1) {
        throw new Error ("CCD patientRole must contain exactly one patient element")
    }
    
    return patientRoles[0]
}

export function readCcdPatientIdentifiers(patientRole: Element): CcdPatientIdentifier[] {
    const idElements = getCdaChildren(patientRole, "id")
    const identifiers: CcdPatientIdentifier[] = [];
    for (const idElement of idElements) {
        if (idElement.getAttribute("nullFlavor") !== null) {
            continue
        }

        const root = idElement.getAttribute("root")
        if (root === null) {
            throw new Error ("Patient identifier must have a non-blank root.")
        }
        if (root.trim() === "") {
            throw new Error ("Patient identifier must have a non-blank root.")
        }

        const extension = idElement.getAttribute("extension")
        if (extension !== null && extension.trim() === "") {
            throw new Error ("Patient identifier extension cannot be blank when present.")
        }
        const identifier: CcdPatientIdentifier = { root: root };
        if (extension !== null) {
            identifier.extension = extension
        }
        identifiers.push(identifier)
    }
    if (identifiers.length === 0) {
        throw new Error ("CCD must contain at least one usable patient identifier")
    }
    return identifiers
}
