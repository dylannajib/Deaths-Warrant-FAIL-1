import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { addHistory, createProfile, readRecordDate, validateProfile } from "./patient-profile";

const fixture = JSON.parse(readFileSync("../tests/fixtures/prognosis/patient-profile.json", "utf8"));

describe("research profile validation", () => {
  it("accepts the shared Python/browser input fixture", () => {
    expect(validateProfile(fixture)).toEqual(fixture);
  });
  it("calculates completed years around birthdays", () => {
    expect(createProfile("1966-02-01", "2026-01-31").ageYears).toBe(59);
    expect(createProfile("1966-02-01", "2026-02-01").ageYears).toBe(60);
    expect(createProfile("1964-02-29", "2025-02-28").ageYears).toBe(60);
  });
  it.each(["2025-02-29", "2026-13-01", "2026", "20260101"])("rejects invalid or incomplete assessment date %s", asOf => {
    expect(() => createProfile(null, asOf)).toThrow();
  });
  it("rejects future birth dates and evidence", () => {
    expect(() => createProfile("2027-01-01", fixture.asOf)).toThrow();
    expect(() => readRecordDate("2027-01-01", fixture.asOf)).toThrow();
  });
  it("accepts supported timezones but rejects invalid times", () => {
    expect(readRecordDate("2025-12-31T23:15:00+11:00", fixture.asOf)).toBe("2025-12-31");
    expect(() => readRecordDate("2025-12-31T29:15:00Z", fixture.asOf)).toThrow();
  });
  it.each([null, 39, 80, 60.5, NaN, Infinity])("rejects unsupported age %s", ageYears => {
    expect(() => validateProfile({ ...fixture, ageYears })).toThrow();
  });
  it.each(["heartFailure", "previousHeartAttack", "previousStroke"])("does not turn missing %s into no", field => {
    expect(() => validateProfile({ ...fixture, [field]: null })).toThrow();
  });
  it("rejects conflicting histories", () => {
    const profile = createProfile(null, fixture.asOf);
    addHistory(profile, "previousStroke", true);
    expect(() => addHistory(profile, "previousStroke", false)).toThrow(/Conflicting/);
  });
});
