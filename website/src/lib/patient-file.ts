export const MAX_PATIENT_FILE_BYTES = 10 * 1024 * 1024;

// Reject empty, oversized or unsupported files before selecting the JSON or XML reader.
export function validatePatientFile(file: Pick<File, "name" | "size">): "json" | "xml" {
  if (file.size > MAX_PATIENT_FILE_BYTES) {
    throw new Error ("Patient record exceeds the supported 10 MiB file limit.")
  }
  if (file.size === 0) {
    throw new Error ("Patient record is empty.")
  }
  const name = file.name.toLowerCase();
  if (name.endsWith(".json")) return "json";
  if (name.endsWith(".xml")) return "xml";
  throw new Error ("Select a supported JSON or XML file")
}
