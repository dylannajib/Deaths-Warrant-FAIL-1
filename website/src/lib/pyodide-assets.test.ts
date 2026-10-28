import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";
import { afterEach, expect, it } from "vitest";
import { preparePyodide } from "../../scripts/prepare-pyodide.mjs";

const manifest = JSON.parse(readFileSync("scripts/pyodide-manifest.json", "utf8"));
const temporary: string[] = [];

// Give each test its own disposable directory without changing installed runtime files.
function directory() {
  const path = mkdtempSync(join(tmpdir(), "dw-pyodide-")); temporary.push(path); return path;
}

// Remove only the unique temporary directories created by this test suite.
afterEach(() => { for (const path of temporary.splice(0)) rmSync(path, { recursive: true, force: true }); });

// Verify the build copies exactly the approved binary files rather than fetching a runtime at visit time.
it("copies the checked local runtime and licence notices", () => {
  const destination = directory();
  preparePyodide(resolve("node_modules/pyodide"), destination);
  for (const [name, checksum] of Object.entries(manifest.files)) {
    expect(createHash("sha256").update(readFileSync(join(destination, name))).digest("hex")).toBe(checksum);
  }
  expect(readFileSync(join(destination, "PYODIDE-LICENSE.txt"), "utf8")).toContain("Mozilla Public License");
  expect(readFileSync(join(destination, "PYTHON-LICENSE.txt"), "utf8")).toContain("PYTHON SOFTWARE FOUNDATION LICENSE");
});

// Fail the build when an installed runtime file differs from the reviewed checksum.
it("refuses a modified runtime before copying assets", () => {
  const source = directory(), destination = directory();
  for (const name of ["package.json", ...Object.keys(manifest.files)]) {
    copyFileSync(join("node_modules/pyodide", name), join(source, name));
  }
  writeFileSync(join(source, "pyodide.js"), "unexpected runtime code");
  expect(() => preparePyodide(source, destination)).toThrow(/checksum mismatch/);
});

// A version update requires deliberately updating the manifest instead of silently changing browsers' Python.
it("refuses a different runtime version", () => {
  const source = directory();
  writeFileSync(join(source, "package.json"), JSON.stringify({ version: "999.0.0" }));
  expect(() => preparePyodide(source, directory())).toThrow(/version/);
});
