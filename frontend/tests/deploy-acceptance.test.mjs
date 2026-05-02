import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

const root = process.cwd();

async function importNextConfig(apiBaseUrl = "https://api.preview.example.com/") {
  process.env.API_BASE_URL = apiBaseUrl;
  const configUrl = pathToFileURL(path.join(root, "next.config.mjs"));
  return import(`${configUrl.href}?acceptance=${Date.now()}${Math.random()}`);
}

async function readSource(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

test("rewrites keep frontend API calls on the deployed FastAPI project", async () => {
  const { default: nextConfig } = await importNextConfig();
  const rewrites = await nextConfig.rewrites();

  assert.deepEqual(rewrites, [
    {
      source: "/api/v1/:path*",
      destination: "https://api.preview.example.com/api/v1/:path*"
    }
  ]);
});

test("deploy headers cache only immutable assets and keep app/payment/API paths private", async () => {
  const { default: nextConfig } = await importNextConfig();
  const headers = await nextConfig.headers();
  const bySource = Object.fromEntries(headers.map((entry) => [entry.source, entry.headers]));

  assert.equal(
    bySource["/_next/static/:path*"][0].value,
    "public, max-age=31536000, immutable"
  );
  assert.equal(bySource["/dashboard"][0].value, "no-store, max-age=0");
  assert.equal(bySource["/auth/verify"][0].value, "no-store, max-age=0");
  assert.equal(bySource["/api/v1/:path*"][0].value, "no-store, max-age=0");
});

test("upload flow validates file type and size before sending to the API", async () => {
  const dropzone = await readSource("components/dashboard/dropzone.tsx");

  assert.match(dropzone, /MAX_FILE_SIZE_BYTES = 5 \* 1024 \* 1024/);
  assert.match(dropzone, /ACCEPTED_EXTENSIONS = \["\.pdf", "\.docx"\]/);
  assert.match(dropzone, /application\/pdf/);
  assert.match(
    dropzone,
    /application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document/
  );
  assert.match(dropzone, /onFileAccepted\(file\)/);
});

test("dashboard gates upload by quota and opens login or paywall paths", async () => {
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");
  const quotaIndex = dashboard.indexOf("const quota = await getAnalysisQuota()");
  const analysisIndex = dashboard.indexOf("const result = await submitResumeForAnalysis(file)");

  assert.ok(quotaIndex > -1, "quota check is present");
  assert.ok(analysisIndex > quotaIndex, "analysis starts only after quota check");
  assert.match(dashboard, /quota\.registration_required/);
  assert.match(dashboard, /router\.replace\("\/login\?reason=free-limit"\)/);
  assert.match(dashboard, /quota\.payment_required/);
  assert.match(dashboard, /setPaywallOpen\(true\)/);
  assert.match(dashboard, /onPaymentConfirmed=\{handlePaymentConfirmed\}/);
});

test("paywall creates PIX charge, listens for confirmation, and handles expiration", async () => {
  const paywall = await readSource("components/dashboard/paywall-modal.tsx");

  assert.match(paywall, /createPixCharge\(\)/);
  assert.match(paywall, /new EventSource\(apiPath\("\/payments\/status-stream"\)/);
  assert.match(paywall, /payment_confirmed/);
  assert.match(paywall, /payment_expired/);
  assert.match(paywall, /markChargeExpired\(\)/);
  assert.match(paywall, /onPaymentConfirmed\(\)/);
});
