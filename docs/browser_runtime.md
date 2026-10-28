# Browser Python hosting

The current Next.js website hosts Pyodide 0.27.7 on the same origin as the application. The legacy `web/` experiment is separate and retains its earlier CDN configuration.

## Build and provenance

- `website/package.json` pins the build dependency `pyodide` to exactly 0.27.7. The npm lockfile records its package integrity.
- `scripts/prepare-pyodide.mjs` verifies the installed version, locked package integrity and each source file's SHA-256 against `scripts/pyodide-manifest.json`. A mismatch fails the build before runtime assets are copied. These checks detect drift from the recorded dependency; they do not establish that upstream software has no vulnerabilities.
- `predev` and `prebuild` invoke the preparation through `prepare-prognosis.mjs`. The five runtime files and notices are copied into ignored `public/vendor/pyodide/0.27.7/`, then exported into `out/`. No participant data is involved.
- MPL, CPython and Emscripten licence texts and their tagged source URLs are retained in `website/vendor-notices/pyodide-0.27.7/` and distributed beside the runtime. Upstream source: https://github.com/pyodide/pyodide/tree/0.27.7 .
- Updating Python requires a deliberate dependency, lockfile, manifest and worker path update followed by browser verification. Do not edit generated or upstream runtime code to match application style.

## Startup check, 28 October 2026

Before this change a real browser worker fetched these five files from `cdn.jsdelivr.net/pyodide/v0.27.7/full/`. After the change the same worker fetched all five from `/vendor/pyodide/0.27.7/` on the application origin:

| File | Bytes before HTTP compression |
| --- | ---: |
| pyodide.js | 14,913 |
| pyodide.asm.js | 1,255,688 |
| pyodide.asm.wasm | 10,105,545 |
| python_stdlib.zip | 2,360,737 |
| pyodide-lock.json | 112,205 |
| Total | 13,849,088 |

At that initial check the browser also fetched local `prognosis/engine.py` and `prognosis/model.json`. The release build now uses hash-named copies selected by `prognosis/assets.json`, with worker-side content verification. Main-page scripts, fonts and CSS were same-origin. Temporary instrumentation was used for the original runtime request audit and was not shipped as application telemetry. The synthetic remaining-years result is unchanged. Restrictive headers are now generated and tested in the local Pages runtime.

The five runtime files total 5,727,646 bytes when individually gzip-compressed for a size estimate. This is not a measured public-host transfer size. The Python HTTP server sends them uncompressed. The Pages local emulator was subsequently verified with actual gzip delivery, immutable versioned files, revalidated mutable files and ETag 304 responses. See `host-verification.json`. One hundred uncached runtime downloads are approximately 1.385 GB uncompressed or 573 MB at the estimated gzip size, excluding other site assets.

## Cost and traffic

Calculations run on each visitor's device, so there is no per-patient Python server process. A static hosting service delivers the software. One hundred simultaneous visitors is a reasonable target for a distributed static host, but no production capacity or 100-browser load test has been performed.

Cloudflare Pages is a possible free hosting target: its documentation lists static asset requests as free and unlimited, with a 25 MiB per-file limit and 500 builds per month on the free plan. Our largest runtime file is below that per-file limit. Hosting terms and limits can change; custom domains may cost money. No account, deployment or paid service has been created.

Sources checked 28 October 2026:

- https://developers.cloudflare.com/pages/functions/pricing/
- https://developers.cloudflare.com/pages/platform/limits/

## Release approval and public checks

Security headers/CSP, benchmarks, cache rules, release validation, local host verification and deployment instructions are complete for review. No production deployment or guarantee of zero vulnerabilities is claimed. Publication requires user approval, followed by the public HTTPS/edge checks and representative mobile observations in `deployment.md`.
