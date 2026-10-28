# Static deployment and approval

The approved static application is published at https://deaths-warrant.pages.dev/ on Cloudflare Pages, with no Functions, application user accounts, database, analytics or patient upload endpoint. The application is a cardiovascular research prototype; publication does not establish clinical suitability.

## Current deployment

Published 28 October 2026 using deployment `34dcc7a4`, from approved code checkpoint `0db6aa0`. Release ID: `92e83cdeb406d4c6b0683db5ad403a41da005e5c253b6a135cf62f492a945d04`. The immutable deployment URL is https://34dcc7a4.deaths-warrant.pages.dev/.

The public host passed byte-for-byte and security/cache/compression checks, including HTTP-to-HTTPS redirection. Desktop and 375-pixel Chromium browser tests passed with synthetic records. Public reports are `public-host-verification.json`, `public-browser-verification.json` and `public-performance-results.json`. Mobile testing used desktop emulation; physical-device coverage remains unmeasured.

Deployment uses the local CLI. GitHub pushes do not automatically publish changes. Cloudflare OAuth credentials are held outside the repository. No API token was added to application code or browser assets. No custom bot challenge or application rate limiter was configured; the site serves static files and has no calculation API. Review host abuse controls if traffic warrants them or before adding endpoints.

## Build and inspect

Use Linux from the repository root:

```bash
.venv/bin/python -m pytest -q
cd website
npm ci --ignore-scripts
npm run typecheck
npm test
npm run lint
npm run build
npm run check:release
npm run preview:production
```

The last command runs the pinned Cloudflare local emulator at `http://127.0.0.1:8004`. It applies the actual Pages `_headers` rules. `next dev` and Python's simple HTTP server do not exercise the production CSP or cache rules. Wrangler metrics are disabled in this command. Local emulator files remain ignored.

In another Linux terminal, from `website/`:

```bash
node scripts/check-host.mjs http://127.0.0.1:8004/ --output ../docs/host-verification.json
node scripts/benchmark-prognosis.mjs --base-url http://127.0.0.1:8004/ --output ../docs/performance-results.json
```

These commands use only software files, a frozen model and synthetic records. Do not substitute patient files for benchmarks, screenshots, CI artifacts or reports.

## What the build enforces

1. `preparePyodide()` checks the locked runtime version and hashes before copying its five files and notices.
2. `prepare-prognosis.mjs` copies the unchanged engine/model into SHA-256 filenames and writes a small `assets.json`. The worker verifies their contents before executing Python or loading coefficients. The manifest is not an independent signature; deployment integrity still depends on the approved build and hosting account.
3. `finaliseExport()` hashes Next's exact inline startup scripts and generates `out/_headers`. No general inline-script or JavaScript-eval permission is granted. `wasm-unsafe-eval` permits the required WebAssembly compilation. Page and worker connections are restricted to the site origin.
4. Versioned runtime/framework assets and hash-named engine/model files are immutable for one year. HTML, the worker, release metadata and the prognosis manifest revalidate. No patient records or calculated results are put in HTTP caches by the application.
5. `checkExport()` verifies the exact release inventory, runtime hashes, frozen model, CSP hashes, asset names and the host's 25 MiB per-file limit. It rejects participant-style data files and unexpected development directories. `out/release.json` identifies this exact artifact.
6. CI performs the checks and retains the static export as a seven-day review artifact. It does not deploy anything automatically. The artifact contains the public software/model, not local participant files.

The minimal custom missing-page component avoids Next's default inline styles, keeping the same restrictive policy on the 404 response. Visual polishing remains milestone 12.

## Publication after approval

For Cloudflare Git integration, use repository root as the root directory, Node `22.22.1`, build command `cd website && npm ci --ignore-scripts && npm run build`, output directory `website/out`, and production branch `main`. Set `NODE_VERSION=22.22.1` if required by the host. Review the project settings before enabling automatic deployment; connecting the production branch can publish immediately.

For a controlled manual deployment, authenticate locally with the pinned CLI after approval, then run from `website/`:

```bash
npx --no-install wrangler login
npm run check:release
npx --no-install wrangler pages deploy out --project-name deaths-warrant
```

The initial publication used this manual flow with the `deaths-warrant` project. Future releases require rebuilding and repeating release checks before deployment. No API token belongs in source control or chat. The free `pages.dev` address avoids a domain purchase; custom domains may have registration costs. There is no paid Python compute component.

Do not enable Web Analytics, Zaraz, Rocket Loader, email obfuscation, HTML rewriting, injected scripts or additional Functions without reviewing privacy and CSP consequences. Deploy the whole `out/` atomically. Preserve the previous approved Pages deployment for rollback; do not manually overwrite files under immutable URLs. A dependency change must get a new versioned path and checked manifest.

## Checks on the approved public URL

After publication, use the same checked artifact and replace the example address:

```bash
node scripts/check-host.mjs https://YOUR-PROJECT.pages.dev/
```

Then repeat the synthetic FHIR/CCD, missing-input, range-error/recovery and Clear checks in a browser. Check Network including worker traffic, storage, CSP console messages and the site's release ID. Verify HTTP redirects to HTTPS and that HSTS is present on HTTPS. Inspect real compression and cache revalidation on the public host. Test a typical mobile device/connection before making startup-time or scale promises.

Local emulator measurements are not a public-edge capacity test, and 100 static requests are not 100 concurrent browser sessions. Published-host checks and mobile observations remain release acceptance steps because they require the approved host to exist.

## Rollback

If synthetic calculations, headers or content hashes differ, stop accepting the new release and restore the previous full Pages deployment using the host's rollback control. Re-run the public-host check and synthetic browser test on the restored version. Keep both release manifests and the failure record. Do not retune the prognosis model to fix a deployment fault.

References checked 28 October 2026:

- https://developers.cloudflare.com/pages/configuration/headers/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/pages/functions/pricing/
