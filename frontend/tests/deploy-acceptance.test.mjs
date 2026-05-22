import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

const root = process.cwd();

async function importNextConfig(options = {}) {
  const normalizedOptions =
    typeof options === "string" ? { apiBaseUrl: options } : options;
  const hasApiBaseUrl = Object.hasOwn(normalizedOptions, "apiBaseUrl");
  const apiBaseUrl = hasApiBaseUrl
    ? normalizedOptions.apiBaseUrl
    : "https://api.preview.example.com/";
  const { vercelEnv } = normalizedOptions;
  const { vercelTargetEnv } = normalizedOptions;
  const previousApiBaseUrl = process.env.API_BASE_URL;
  const previousVercelEnv = process.env.VERCEL_ENV;
  const previousVercelTargetEnv = process.env.VERCEL_TARGET_ENV;

  if (apiBaseUrl === undefined) {
    delete process.env.API_BASE_URL;
  } else {
    process.env.API_BASE_URL = apiBaseUrl;
  }

  if (vercelEnv === undefined) {
    delete process.env.VERCEL_ENV;
  } else {
    process.env.VERCEL_ENV = vercelEnv;
  }

  if (vercelTargetEnv === undefined) {
    delete process.env.VERCEL_TARGET_ENV;
  } else {
    process.env.VERCEL_TARGET_ENV = vercelTargetEnv;
  }

  const configUrl = pathToFileURL(path.join(root, "next.config.mjs"));
  try {
    return await import(`${configUrl.href}?acceptance=${Date.now()}${Math.random()}`);
  } finally {
    restoreEnv("API_BASE_URL", previousApiBaseUrl);
    restoreEnv("VERCEL_ENV", previousVercelEnv);
    restoreEnv("VERCEL_TARGET_ENV", previousVercelTargetEnv);
  }
}

function restoreEnv(name, value) {
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
}

async function readSource(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

function expectedApiRewrites(apiBaseUrl) {
  return [
    "/api/v1/auth/request-link",
    "/api/v1/auth/session",
    "/api/v1/auth/logout",
    "/api/v1/analysis",
    "/api/v1/analysis/:path*",
    "/api/v1/payments/create-charge",
    "/api/v1/payments/status-stream"
  ].map((source) => ({
    source,
    destination: `${apiBaseUrl}${source}`
  }));
}

test("rewrites keep frontend API calls on the deployed FastAPI project", async () => {
  const { default: nextConfig } = await importNextConfig();
  const rewrites = await nextConfig.rewrites();

  assert.deepEqual(rewrites, expectedApiRewrites("https://api.preview.example.com"));
  assert.equal(
    rewrites.some((rewrite) => rewrite.source === "/api/v1/payments/webhook"),
    false
  );
});

test("production rewrites use the canonical API alias instead of immutable deployment URLs", async () => {
  const { default: nextConfig } = await importNextConfig({
    apiBaseUrl: "https://parserly-g2b4ih1a1-kaikerods-projects.vercel.app",
    vercelEnv: "production"
  });
  const rewrites = await nextConfig.rewrites();

  assert.deepEqual(rewrites, expectedApiRewrites("https://parserly-api.vercel.app"));
});

test("production target rewrites use the canonical API alias for immutable deployment URLs", async () => {
  const { default: nextConfig } = await importNextConfig({
    apiBaseUrl: "https://parserly-g2b4ih1a1-kaikerods-projects.vercel.app/",
    vercelTargetEnv: "production"
  });
  const rewrites = await nextConfig.rewrites();

  assert.deepEqual(rewrites, expectedApiRewrites("https://parserly-api.vercel.app"));
});

test("production rewrites default to the canonical API alias on Vercel", async () => {
  const { default: nextConfig } = await importNextConfig({
    apiBaseUrl: undefined,
    vercelEnv: "production"
  });
  const rewrites = await nextConfig.rewrites();

  assert.deepEqual(rewrites, expectedApiRewrites("https://parserly-api.vercel.app"));
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
  assert.ok(
    bySource["/(.*)"].some(
      (header) =>
        header.key === "Strict-Transport-Security" &&
        header.value === "max-age=31536000; includeSubDomains; preload"
    )
  );
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

test("authenticated dashboard loads and opens persistent analysis history", async () => {
  const api = await readSource("lib/api.ts");
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");

  assert.match(api, /export async function listAnalyses/);
  assert.match(api, /export async function getAnalysisById/);
  assert.match(api, /apiPath\(`\/analysis\?\$\{params\.toString\(\)\}`\)/);
  assert.match(api, /apiPath\(`\/analysis\/\$\{encodeURIComponent\(id\)\}`\)/);

  assert.match(dashboard, /const history = await listAnalyses\(10, 0, \{ signal \}\)/);
  assert.match(dashboard, /if \(!isAuthenticated \|\| isLoadingAuth\) \{\s+return;\s+\}/);
  assert.match(dashboard, /const \[isLoadingData, setIsLoadingData\] = useState\(false\)/);
  assert.match(dashboard, /void loadAnalysisHistory\(\)/);
  assert.match(
    dashboard,
    /const savedAnalysis = await getAnalysisById\(item\.id, \{ signal: controller\.signal \}\)/
  );
  assert.match(dashboard, /<AnalysisHistoryPanel/);
  assert.match(dashboard, /items=\{analysisHistory\}/);
});

test("dashboard resolves auth session before exposing guest navigation", async () => {
  const api = await readSource("lib/api.ts");
  const hook = await readSource("hooks/use-auth-session.ts");
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");

  assert.match(api, /export async function getAuthSession/);
  assert.match(api, /apiPath\("\/auth\/session"\)/);
  assert.match(api, /credentials: "include"/);
  assert.match(api, /cache: "no-store"/);

  assert.match(hook, /export interface AuthSessionState/);
  assert.match(hook, /isAuthenticated: boolean/);
  assert.match(hook, /isLoadingAuth: boolean/);
  assert.match(hook, /authError: string \| null/);
  assert.match(hook, /refreshSession: \(\) => Promise<void>/);
  assert.match(hook, /logout: \(\) => Promise<void>/);
  assert.match(hook, /void resolveSession\(controller\.signal\)/);

  assert.match(dashboard, /isLoadingAuth \? \(/);
  assert.match(dashboard, /Confirmando sessao/);
  assert.match(dashboard, /\) : isAuthenticated \? \(/);
  assert.match(dashboard, /href="\/login"/);
});

test("dashboard history fetches only after confirmed auth and ignores stale requests", async () => {
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");

  assert.match(dashboard, /if \(!isAuthenticated \|\| isLoadingAuth\) \{\s+return;\s+\}/);
  assert.match(dashboard, /new AbortController\(\)/);
  assert.match(dashboard, /controller\.abort\(\)/);
  assert.match(dashboard, /historyRequestRef\.current !== requestId/);
  assert.match(dashboard, /getAnalysisById\(item\.id, \{ signal: controller\.signal \}\)/);
  assert.match(dashboard, /isAuthLoading=\{isLoadingAuth\}/);
  assert.match(dashboard, /!isAuthLoading && !isLoading && items\.length === 0/);
});

test("dashboard logout clears user-specific history and selected report state", async () => {
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");

  const clearIndex = dashboard.indexOf("clearUserSpecificState();");
  const logoutIndex = dashboard.indexOf("await endSession();");

  assert.ok(clearIndex > -1, "clearUserSpecificState is called");
  assert.ok(logoutIndex > clearIndex, "session logout runs after user-specific state is cleared");
  assert.match(dashboard, /setAnalysisHistory\(\[\]\)/);
  assert.match(dashboard, /setHistoryTotal\(0\)/);
  assert.match(dashboard, /setSelectedHistoryId\(null\)/);
  assert.match(dashboard, /setHistoryError\(null\)/);
  assert.match(dashboard, /setAnalysis\(null\)/);
});

test("login page is framed as unified passwordless access", async () => {
  const loginClient = await readSource("components/auth/login-client.tsx");
  const loginPage = await readSource("app/login/page.tsx");

  assert.match(loginClient, /Login por magic link/);
  assert.match(loginClient, /Acesso por e-mail/);
  assert.match(loginClient, /Se for seu primeiro acesso, o Parserly cria sua conta ao verificar o link/);
  assert.match(loginClient, /Cadastro por magic link/);
  assert.doesNotMatch(loginClient, /error\.status === 404/);
  assert.doesNotMatch(loginClient, /contas já cadastradas/);
  assert.match(loginPage, /Entre ou crie acesso no Parserly por magic link/);
  assert.match(loginPage, /const isRegistrationIntent = intentCode === "registration" \|\| reasonCode === "free-limit"/);
  assert.match(loginPage, /intent=\{isRegistrationIntent \? "registration" : "login"\}/);
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
