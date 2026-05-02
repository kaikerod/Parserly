import { readFile } from "node:fs/promises";
import path from "node:path";
import { File } from "node:buffer";

const DEFAULT_TIMEOUT_MS = 20_000;
const FORBIDDEN_HEALTH_TOKENS = [
  "OPENROUTER_API_KEY",
  "RESEND_API_KEY",
  "ABACATEPAY_API_KEY",
  "ABACATEPAY_WEBHOOK_SECRET",
  "SECRET_KEY",
  "DATABASE_URL",
  "REDIS_URL"
];

async function main() {
  const apiUrl = requiredUrl("API_PREVIEW_URL");
  const frontendUrl = requiredUrl("FRONTEND_PREVIEW_URL");

  await checkApiHealth(apiUrl);
  await checkFrontendHome(frontendUrl);

  if (process.env.SMOKE_TEST_EMAIL) {
    await checkMagicLinkRequest(apiUrl, process.env.SMOKE_TEST_EMAIL);
  } else {
    console.log("smoke: skipping magic link request because SMOKE_TEST_EMAIL is not set");
  }

  if (process.env.SMOKE_UPLOAD_FIXTURE) {
    await checkUpload(apiUrl, process.env.SMOKE_UPLOAD_FIXTURE);
  } else {
    console.log("smoke: skipping upload because SMOKE_UPLOAD_FIXTURE is not set");
  }

  console.log("smoke: preview acceptance checks passed");
}

function requiredUrl(name) {
  const rawValue = process.env[name];
  if (!rawValue) {
    throw new Error(`Set ${name} before running smoke tests.`);
  }

  const url = new URL(rawValue);
  url.pathname = url.pathname.replace(/\/+$/, "");
  return url.toString().replace(/\/$/, "");
}

async function checkApiHealth(apiUrl) {
  const response = await fetchWithTimeout(`${apiUrl}/health`, {
    headers: { Accept: "application/json" }
  });
  const body = await response.text();

  assertOk(response, "GET /health");
  const payload = parseJson(body, "GET /health");
  if (payload.status !== "ok") {
    throw new Error(`GET /health returned status=${JSON.stringify(payload.status)}`);
  }

  const serializedPayload = JSON.stringify(payload);
  for (const forbiddenToken of FORBIDDEN_HEALTH_TOKENS) {
    if (serializedPayload.includes(forbiddenToken)) {
      throw new Error(`GET /health leaked ${forbiddenToken}`);
    }
  }

  console.log("smoke: API health is ok");
}

async function checkFrontendHome(frontendUrl) {
  const response = await fetchWithTimeout(`${frontendUrl}/`, {
    headers: { Accept: "text/html" }
  });
  const body = await response.text();

  assertOk(response, "GET /");
  if (!body.includes("Parserly")) {
    throw new Error("GET / did not render the Parserly frontend shell.");
  }

  console.log("smoke: frontend home renders");
}

async function checkMagicLinkRequest(apiUrl, email) {
  const response = await fetchWithTimeout(`${apiUrl}/api/v1/auth/request-link`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ email })
  });
  const body = await response.text();

  if (response.status !== 202) {
    throw new Error(`POST /api/v1/auth/request-link returned ${response.status}: ${body}`);
  }

  const payload = parseJson(body, "POST /api/v1/auth/request-link");
  if (typeof payload.expires_in !== "number" || payload.expires_in <= 0) {
    throw new Error("Magic link response did not include a positive expires_in value.");
  }

  console.log("smoke: magic link request accepted");
}

async function checkUpload(apiUrl, fixturePath) {
  const absoluteFixturePath = path.resolve(fixturePath);
  const fileBytes = await readFile(absoluteFixturePath);
  const fileName = path.basename(absoluteFixturePath);
  const formData = new FormData();
  formData.set("file", new File([fileBytes], fileName, { type: contentTypeFor(fileName) }));

  const response = await fetchWithTimeout(
    `${apiUrl}/api/v1/analysis`,
    {
      method: "POST",
      body: formData
    },
    90_000
  );
  const body = await response.text();

  if (response.status !== 201) {
    throw new Error(`POST /api/v1/analysis returned ${response.status}: ${body}`);
  }

  const payload = parseJson(body, "POST /api/v1/analysis");
  if (typeof payload.score !== "number" || !payload.report_json) {
    throw new Error("Upload response did not include score and report_json.");
  }

  console.log("smoke: upload analysis accepted");
}

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      redirect: "follow",
      ...options,
      signal: controller.signal
    });
  } finally {
    clearTimeout(timeout);
  }
}

function assertOk(response, label) {
  if (!response.ok) {
    throw new Error(`${label} returned HTTP ${response.status}`);
  }
}

function parseJson(rawBody, label) {
  try {
    return JSON.parse(rawBody);
  } catch (error) {
    throw new Error(`${label} did not return valid JSON: ${error.message}`);
  }
}

function contentTypeFor(fileName) {
  if (fileName.toLowerCase().endsWith(".pdf")) {
    return "application/pdf";
  }
  if (fileName.toLowerCase().endsWith(".docx")) {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  return "application/octet-stream";
}

main().catch((error) => {
  console.error(`smoke: ${error.message}`);
  process.exitCode = 1;
});
