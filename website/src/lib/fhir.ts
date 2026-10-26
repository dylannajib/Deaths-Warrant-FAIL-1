function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isFhirBundle(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    "resourceType" in value &&
    value.resourceType === "Bundle"
  );
}

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
    if (entry.resource.resourceType.trim() !== "") {
      throw new Error ("Detected empty string and spaces.")
    }
    resources.push(entry.resource)
  }
  return (resources)
}