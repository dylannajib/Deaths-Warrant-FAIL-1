import { get as httpGet } from "node:http";
import { get as httpsGet } from "node:https";
import { gunzipSync, brotliDecompressSync, inflateSync } from "node:zlib";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checkExport } from "./check-export.mjs";

const scripts = dirname(fileURLToPath(import.meta.url));

// Read a bounded static response, recording wire bytes separately from decoded content.
function requestAsset(url, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const get = url.protocol === "https:" ? httpsGet : httpGet;
    const request = get(url, { headers: { "Accept-Encoding": "gzip", ...extraHeaders } }, response => {
      const chunks = []; let size = 0;
      // Stop oversized responses before retaining more than the supported static-file budget.
      response.on("data", chunk => {
        size += chunk.length;
        if (size > 26 * 1024 * 1024) request.destroy(new Error("Hosted asset exceeds the check limit."));
        else chunks.push(chunk);
      });
      // Propagate aborted response streams to the verification command.
      response.on("error", reject);
      // Decode completed static responses only after collecting their bounded body.
      response.on("end", () => {
        try {
          const raw = Buffer.concat(chunks), encoding = response.headers["content-encoding"];
          const limit = { maxOutputLength: 26 * 1024 * 1024 };
          const body = raw.length === 0 ? raw : encoding === "gzip" ? gunzipSync(raw, limit) : encoding === "br" ? brotliDecompressSync(raw, limit)
            : encoding === "deflate" ? inflateSync(raw, limit) : raw;
          resolve({ status: response.statusCode, headers: response.headers, body, wireBytes: raw.length });
        } catch (error) { reject(error); }
      });
    });
    request.setTimeout(15000, () => request.destroy(new Error("Hosted asset timed out.")));
    // Report connection failures instead of leaving the check pending.
    request.on("error", reject);
  });
}

// Verify the exact prepared export, security headers, cache semantics and compression on a chosen host.
async function main() {
  const [address = "http://127.0.0.1:8004/", flag, output] = process.argv.slice(2);
  const base = new URL(address);
  if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || base.search || base.hash ||
    !base.pathname.endsWith("/") || (flag !== undefined && (flag !== "--output" || !output))) throw new Error("Use BASE_URL/ [--output PATH] without credentials or query strings.");
  const release = checkExport();
  const manifest = JSON.parse(readFileSync(join(scripts, "../out/release.json"), "utf8"));
  const expectedPolicy = readFileSync(join(scripts, "../out/_headers"), "utf8").split("\n")
    .find(line => line.trimStart().startsWith("Content-Security-Policy:")).trim().slice("Content-Security-Policy: ".length);
  const required = { "x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-origin", "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "strict-transport-security": "max-age=31536000",
    "content-security-policy": expectedPolicy };
  const records = [];
  const entries = Object.entries(manifest.files).filter(([name]) => name !== "_headers" && (!name.endsWith(".html") || name === "index.html"));
  for (const [name, expected] of entries) {
    const response = await requestAsset(new URL(name === "index.html" ? "" : name, base));
    if (response.status !== 200) throw new Error("Unexpected hosted status for " + name + ": " + response.status);
    if (createHash("sha256").update(response.body).digest("hex") !== expected.sha256) throw new Error("Hosted content differs: " + name);
    for (const [header, value] of Object.entries(required)) if (response.headers[header] !== value) throw new Error("Incorrect hosted header: " + header + " for " + name);
    const immutable = name.startsWith("_next/static/") || name.startsWith("vendor/") || /^prognosis\/(engine|model)\.[a-f0-9]{64}\./.test(name);
    if (response.headers["cache-control"] !== (immutable ? "public, max-age=31536000, immutable" : "no-cache") &&
      ["index.html", "prognosis-worker.js", "prognosis/assets.json"].includes(name)) throw new Error("Mutable asset cache rule failed: " + name);
    if (immutable && response.headers["cache-control"] !== "public, max-age=31536000, immutable") throw new Error("Immutable cache rule failed: " + name);
    if (name.endsWith(".wasm") && response.headers["content-type"] !== "application/wasm") throw new Error("Incorrect WebAssembly MIME type.");
    records.push({ file: name, decodedBytes: response.body.length, wireBytes: response.wireBytes,
      encoding: response.headers["content-encoding"] ?? "identity", cache: response.headers["cache-control"] ?? null });
  }
  const modelName = entries.find(([name]) => /^prognosis\/model\./.test(name))[0];
  const modelUrl = new URL(modelName, base), first = await requestAsset(modelUrl);
  if (!first.headers.etag) throw new Error("Host supplied no ETag for revalidation.");
  const revalidated = await requestAsset(modelUrl, { "If-None-Match": first.headers.etag });
  if (revalidated.status !== 304) throw new Error("Host did not honour ETag revalidation.");
  const missing = await requestAsset(new URL("__missing_release_probe__", base));
  if (missing.status !== 404 || missing.headers["content-security-policy"] !== expectedPolicy) throw new Error("Missing-page security response failed.");
  if (!records.some(record => record.file.endsWith(".wasm") && record.encoding === "gzip")) throw new Error("Host did not compress the large WebAssembly asset.");
  const result = { measuredAt: new Date().toISOString(), base: base.href, releaseId: release.id, filesChecked: records.length,
    headersPassed: true, exactContentPassed: true, etagStatus: revalidated.status, notFoundStatus: missing.status,
    wireBytes: records.reduce((sum, item) => sum + item.wireBytes, 0),
    scope: base.protocol === "http:" ? "Local HTTP verification only; public HTTPS and edge behaviour require post-deployment verification." : "Verification of the specified HTTPS host at the recorded time.", records };
  if (output) writeFileSync(output, JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result, null, 2));
}

main().catch(error => { console.error(String(error)); process.exitCode = 1; });
