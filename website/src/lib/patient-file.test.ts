import { describe, expect, it } from "vitest";
import { MAX_PATIENT_FILE_BYTES, validatePatientFile } from "./patient-file";

describe("patient file limits before reading", () => {
  it.each(["record.json", "record.JSON", "record.xml", "record.XML"])("recognises supported file %s", name => {
    expect(validatePatientFile({ name, size: 100 })).toBe(name.toLowerCase().endsWith("json") ? "json" : "xml");
  });
  it("accepts the exact size boundary and rejects larger records", () => {
    expect(validatePatientFile({ name: "record.json", size: MAX_PATIENT_FILE_BYTES })).toBe("json");
    expect(() => validatePatientFile({ name: "record.json", size: MAX_PATIENT_FILE_BYTES + 1 })).toThrow(/10 MiB/);
  });
  it("rejects empty and unsupported files", () => {
    expect(() => validatePatientFile({ name: "empty.json", size: 0 })).toThrow(/empty/);
    expect(() => validatePatientFile({ name: "record.csv", size: 100 })).toThrow(/JSON or XML/);
    expect(() => validatePatientFile({ name: "record.json.exe", size: 100 })).toThrow(/JSON or XML/);
  });
});
