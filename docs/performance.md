# Milestone 11.5 measurements

Measured 28 October 2026 on this desktop under WSL2, Node 22.22.1 and Pyodide 0.27.7. These results do not represent mobile devices or public-network latency. No participant data, fitting or final outcome inspection was involved.

| Measurement | Result |
| --- | ---: |
| Fresh Node runtime plus engine/model | 2.38 s |
| Node, 100 warm predictions: mean / p95 | 2.57 / 3.57 ms |
| Fresh incognito browser worker against local Pages: ready | 4.96 s |
| Browser, 100 predictions including messages: mean / p95 | 5.52 / 7.90 ms |
| Local static delivery, 100 concurrent model GETs | 100 HTTP 200 responses |
| That static batch: wall time / p95 latency | 0.833 s / 0.810 s |

Full results and environment/source hashes are in `performance-results.json` and `browser-verification.json`. The static test follows the local `assets.json` to the hash-named model. It measures one small static asset, not 100 simultaneous browsers or Python instances. No production capacity claim follows from it.

The Node test includes JSON bridging, inference, 100-bootstrap fitted-mean uncertainty and result checks. A new runtime is cold at the process level, but operating-system caches are not cleared. Eight supported boundary profiles had finite outputs. Six invalid profiles were rejected and each was followed by a successful calculation.

The real TypeScript reader parsed the shared 6,317-byte FHIR fixture in a mean 0.23 ms. A deliberately invalid 1,001-entry bundle was rejected for repeated evidence in a mean 4.04 ms. This larger negative test does not establish support for large clinical exports. Valid import recovered afterwards.

In the browser, the synthetic profile returned exactly 17.435570518699695 mean years, matching local Python. Startup was measured from constructing the real worker until its ready message in a fresh incognito browser context. Inference was measured through 100 request/result round trips. No CPU/network throttling or mobile hardware was simulated.

## Repeat

From `website/` after installing locked dependencies:

```bash
node scripts/benchmark-prognosis.mjs --output ../docs/performance-results.json
```

With `npm run preview:production` running in another terminal:

```bash
node scripts/benchmark-prognosis.mjs --base-url http://127.0.0.1:8004/ --output ../docs/performance-results.json
node scripts/check-host.mjs http://127.0.0.1:8004/ --output ../docs/host-verification.json
```

The benchmark exits unsuccessfully on calculation/validation failures. Optional static HTTP failures are reported in `staticRequests.allSuccessful` and status counts, so inspect that flag. Each static request has a 15-second deadline. Reports contain aggregate measurements, synthetic source hashes and software filenames, not records or individual patient predictions.

The host verifier checked 53 served files against the release, plus ETag 304 and missing-page 404 responses. It verified security and cache headers, WebAssembly content type and actual gzip delivery. It received 6,259,620 encoded body bytes across those files, excluding headers. This reflects the local emulator's compression and excludes the alternate HTML routes, not a universal first-visit download figure. The public host may compress/cache differently.

Security headers, worker readiness, complete FHIR/CCD calculations, missing answers, range-error recovery, malformed XML and Clear were also checked in the real browser. New inline scripts and external connections were deliberately probed and blocked. The two expected CSP violations were test evidence, not application failures.

## Public release observations

The approved build was published at https://deaths-warrant.pages.dev/ on 28 October 2026. `public-host-verification.json` records 53 exact-file/security checks, ETag 304 and secured 404 responses. HTTP redirects to HTTPS. The checked files totalled 6,150,931 encoded body bytes on this connection, excluding headers and alternate HTML routes.

All 100 concurrent public model GETs succeeded; batch wall time was 6.28 s and p95 was 5.97 s. See `public-performance-results.json`. This is one static-file batch, not 100 simultaneous browser/Python sessions or a capacity guarantee.

An isolated Chromium context used a 375-by-667 mobile viewport, fourfold CPU slowdown, 200,000 bytes/s page download and 150 ms latency. Model readiness took 33.81 s. Page-level throttling may not cover every worker request. The form/results fitted the viewport, and both record formats, missing inputs, rejection/recovery and Clear passed. Worker-inclusive request capture showed no import/calculation requests and only same-origin software GETs at startup/Clear. See `public-browser-verification.json`.

These mobile observations use desktop emulation. Physical-phone performance, other browser engines and universal startup latency remain unmeasured; none is a release claim.
