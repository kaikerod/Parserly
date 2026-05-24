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
    "/api/v1/auth/google/start",
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

test("deploy headers leave Next static chunks managed and keep app/payment/API paths private", async () => {
  const { default: nextConfig } = await importNextConfig();
  const headers = await nextConfig.headers();
  const bySource = Object.fromEntries(headers.map((entry) => [entry.source, entry.headers]));

  assert.equal(bySource["/_next/static/:path*"], undefined);
  assert.equal(bySource["/icon.svg"][0].value, "public, max-age=31536000, immutable");
  assert.equal(bySource["/dashboard"][0].value, "no-store, max-age=0");
  assert.equal(bySource["/auth/verify"][0].value, "no-store, max-age=0");
  assert.equal(bySource["/auth/google/callback"][0].value, "no-store, max-age=0");
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

test("dashboard shows staged analysis loading and cleans it up on exit", async () => {
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");
  const steps = [
    "Analisando seu currículo",
    "Analisando sua experiência",
    "Extraindo suas habilidades",
    "Gerando recomendações"
  ];
  const stepIndexes = steps.map((step) => dashboard.indexOf(`"${step}"`));

  stepIndexes.forEach((index, stepIndex) => {
    assert.ok(index > -1, `loading step ${stepIndex + 1} is present`);
    if (stepIndex > 0) {
      assert.ok(index > stepIndexes[stepIndex - 1], `loading step ${stepIndex + 1} is ordered`);
    }
  });

  assert.match(
    dashboard,
    /const \[activeAnalysisLoadingStepIndex, setActiveAnalysisLoadingStepIndex\] = useState\(0\)/
  );
  assert.match(
    dashboard,
    /if \(!isSubmitting\) \{\s+setActiveAnalysisLoadingStepIndex\(0\);\s+return;\s+\}/
  );
  assert.match(dashboard, /window\.setTimeout\(\(\) => \{/);
  assert.match(
    dashboard,
    /Math\.min\(currentIndex \+ 1, ANALYSIS_LOADING_STEPS\.length - 1\)/
  );
  assert.match(dashboard, /window\.clearTimeout\(loadingStepTimer\)/);
  assert.match(dashboard, /const result = await submitResumeForAnalysis\(file\)/);
  assert.match(dashboard, /setAnalysis\(result\)/);
  assert.match(dashboard, /finally \{\s+setIsSubmitting\(false\);\s+\}/);

  assert.match(dashboard, /<AnalysisLoadingBanner/);
  assert.match(dashboard, /activeStep=\{activeAnalysisLoadingStep\}/);
  assert.match(dashboard, /afterPayment=\{submissionMode === "after-payment"\}/);
  assert.match(dashboard, /<AnalysisReportLoadingState/);
  assert.match(dashboard, /steps=\{ANALYSIS_LOADING_STEPS\}/);
  assert.match(dashboard, /role="status"/);
  assert.match(dashboard, /aria-live="polite"/);
  assert.match(dashboard, /aria-busy=\{isSubmitting\}/);
  assert.match(dashboard, /disabled=\{isSubmitting\}\s+selectedFile=\{selectedFile\}/);
  assert.match(dashboard, /disabled=\{isSubmitting \|\| !selectedFile\}/);
});

test("dashboard gates upload by quota and opens login or paywall paths", async () => {
  const dashboard = await readSource("components/dashboard/dashboard-client.tsx");
  const quotaIndex = dashboard.indexOf("const quota = await getAnalysisQuota()");
  const analysisIndex = dashboard.indexOf("const result = await submitResumeForAnalysis(file)");

  assert.ok(quotaIndex > -1, "quota check is present");
  assert.ok(analysisIndex > quotaIndex, "analysis starts only after quota check");
  assert.match(dashboard, /quota\.registration_required/);
  assert.match(dashboard, /router\.replace\("\/login\?reason=free-limit"\)/);
  assert.match(dashboard, /label: "Teste grátis", value: "Sem login"/);
  assert.match(dashboard, /label: "Após limite", value: "Google", detail: "ou magic link"/);
  assert.doesNotMatch(dashboard, /magic link por e-mail/);
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

  assert.match(dashboard, /const HISTORY_PAGE_SIZE = 4;/);
  assert.match(
    dashboard,
    /const history = await listAnalyses\(HISTORY_PAGE_SIZE, page \* HISTORY_PAGE_SIZE, \{ signal \}\)/
  );
  assert.match(dashboard, /if \(!isAuthenticated \|\| isLoadingAuth\) \{\s+return;\s+\}/);
  assert.match(dashboard, /const \[isLoadingData, setIsLoadingData\] = useState\(false\)/);
  assert.match(dashboard, /const \[historyPage, setHistoryPage\] = useState\(0\)/);
  assert.match(dashboard, /void loadAnalysisHistory\(0\)/);
  assert.match(dashboard, /setHistoryPage\(0\)/);
  assert.match(
    dashboard,
    /const savedAnalysis = await getAnalysisById\(item\.id, \{ signal: controller\.signal \}\)/
  );
  assert.match(dashboard, /<AnalysisHistoryPanel/);
  assert.match(dashboard, /items=\{analysisHistory\}/);
  assert.match(dashboard, /currentPage=\{historyPage\}/);
  assert.match(dashboard, /pageSize=\{HISTORY_PAGE_SIZE\}/);
  assert.match(dashboard, /onPageChange=\{setHistoryPage\}/);
  assert.match(dashboard, /Mostrando \{startItem\}-\{endItem\} de \{total\}/);
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
  assert.match(hook, /accessLevel: AuthAccessLevel \| null/);
  assert.match(hook, /permissions: AuthPermission\[\]/);
  assert.match(hook, /hasFullAccess: boolean/);
  assert.match(hook, /setAccessLevel\(session\.access_level \?\? null\)/);
  assert.match(hook, /setPermissions\(session\.permissions \?\? \[\]\)/);
  assert.match(hook, /refreshSession: \(\) => Promise<void>/);
  assert.match(hook, /logout: \(\) => Promise<void>/);
  assert.match(hook, /void resolveSession\(controller\.signal\)/);

  assert.match(dashboard, /isLoadingAuth \? \(/);
  assert.match(dashboard, /Confirmando sessao/);
  assert.match(dashboard, /\) : isAuthenticated \? \(/);
  assert.match(dashboard, /permissions\.includes\(ALL_FEATURES_PERMISSION\)/);
  assert.match(dashboard, /\{accessLevel\}/);
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

test("login page is framed as Google-first passwordless access", async () => {
  const loginClient = await readSource("components/auth/login-client.tsx");
  const loginPage = await readSource("app/login/page.tsx");

  assert.match(loginClient, /Login com Google ou magic link/);
  assert.match(loginClient, /Acesso com Google/);
  assert.match(loginClient, /label: "Acesso", value: "Google"/);
  assert.match(loginClient, /label: "Alternativa", value: "magic link"/);
  assert.match(loginClient, /Se for seu primeiro acesso, o Parserly cria sua conta ao verificar o link/);
  assert.match(loginClient, /Cadastro com Google ou magic link/);
  assert.doesNotMatch(loginClient, /error\.status === 404/);
  assert.doesNotMatch(loginClient, /contas já cadastradas/);
  assert.match(loginPage, /Entre ou crie acesso no Parserly com Google ou magic link/);
  assert.match(loginPage, /const isRegistrationIntent = intentCode === "registration" \|\| reasonCode === "free-limit"/);
  assert.match(loginPage, /intent=\{isRegistrationIntent \? "registration" : "login"\}/);
});

test("login page shows Google OAuth access next to magic link", async () => {
  const loginClient = await readSource("components/auth/login-client.tsx");
  const loginPage = await readSource("app/login/page.tsx");
  const api = await readSource("lib/api.ts");

  assert.match(api, /export function googleOAuthStartPath/);
  assert.match(api, /CANONICAL_APP_ORIGIN = "https:\/\/www\.parserly\.com\.br"/);
  assert.match(api, /publicAppPath\(apiPath\("\/auth\/google\/start"\)\)/);
  assert.match(api, /apiPath\("\/auth\/google\/start"\)/);
  assert.match(loginClient, /href=\{googleOAuthStartPath\(\)\}/);
  assert.match(loginClient, /Continuar com Google/);
  assert.match(loginClient, /Cadastrar com Google/);
  assert.doesNotMatch(loginPage, /NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED/);
});

test("production auth entry points redirect to the canonical app domain before cookies", async () => {
  const proxy = await readSource("proxy.ts");
  const verifyRoute = await readSource("app/auth/verify/route.ts");
  const googleCallbackRoute = await readSource("app/auth/google/callback/route.ts");

  assert.match(proxy, /CANONICAL_APP_ORIGIN = "https:\/\/www\.parserly\.com\.br"/);
  assert.match(proxy, /"\/auth\/verify"/);
  assert.match(proxy, /"\/auth\/google\/callback"/);
  assert.match(proxy, /"\/api\/v1\/auth\/google\/start"/);
  assert.match(proxy, /NextResponse\.redirect\(canonicalUrl, 307\)/);
  assert.match(verifyRoute, /CANONICAL_APP_BASE_URL = "https:\/\/www\.parserly\.com\.br"/);
  assert.match(googleCallbackRoute, /CANONICAL_APP_BASE_URL = "https:\/\/www\.parserly\.com\.br"/);
});

test("Google OAuth callback forwards cookies and maps safe errors", async () => {
  const callbackRoute = await readSource("app/auth/google/callback/route.ts");
  const loginPage = await readSource("app/login/page.tsx");

  assert.match(callbackRoute, /forwardSearchParam\(request, callbackUrl, "code"\)/);
  assert.match(callbackRoute, /forwardSearchParam\(request, callbackUrl, "state"\)/);
  assert.match(callbackRoute, /forwardSearchParam\(request, callbackUrl, "error"\)/);
  assert.match(callbackRoute, /Cookie: cookieHeader/);
  assert.match(callbackRoute, /appendSetCookieHeaders\(response, backendResponse\)/);
  assert.match(callbackRoute, /getSetCookie/);
  assert.match(callbackRoute, /NextResponse\.redirect\(createPublicUrl\(request, "\/dashboard"\)\)/);
  assert.match(callbackRoute, /"google-oauth-invalid-state"/);
  assert.match(callbackRoute, /"google-oauth-denied"/);
  assert.match(callbackRoute, /"google-email-unverified"/);
  assert.match(callbackRoute, /"google-account-conflict"/);
  assert.match(callbackRoute, /"google-oauth-unavailable"/);

  assert.match(loginPage, /"google-oauth-invalid-state"/);
  assert.match(loginPage, /"google-oauth-denied"/);
  assert.match(loginPage, /"google-email-unverified"/);
  assert.match(loginPage, /"google-account-conflict"/);
  assert.match(loginPage, /"google-oauth-unavailable"/);
});

test("paywall creates PIX charge, listens for confirmation, and handles expiration", async () => {
  const paywall = await readSource("components/dashboard/paywall-modal.tsx");

  assert.match(paywall, /createPixCharge\(\)/);
  assert.match(paywall, /new EventSource\(apiPath\("\/payments\/status-stream"\)/);
  assert.match(paywall, /payment_confirmed/);
  assert.match(paywall, /payment_expired/);
  assert.match(paywall, /quota\.unlimited_analyses \|\| quota\.remaining_analyses > 0/);
  assert.match(paywall, /markChargeExpired\(\)/);
  assert.match(paywall, /onPaymentConfirmed\(\)/);
});
