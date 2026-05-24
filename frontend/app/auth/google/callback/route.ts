import { NextRequest, NextResponse } from "next/server";
import type { GoogleOAuthCallbackResponse } from "@/types/auth";

const LOCAL_API_BASE_URL = "http://localhost:8000";
const CANONICAL_API_BASE_URL = "https://parserly-api.vercel.app";
const CANONICAL_APP_BASE_URL = "https://www.parserly.com.br";
const PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX = "parserly-";
const VERCEL_TEAM_HOST_SUFFIX = "-kaikerods-projects.vercel.app";
const API_BASE_URL = resolveApiBaseUrl();

export const dynamic = "force-dynamic";

const LOGIN_ERROR_CODES = new Set([
  "google-oauth-invalid-state",
  "google-oauth-denied",
  "google-email-unverified",
  "google-account-conflict",
  "google-oauth-unavailable"
]);

export async function GET(request: NextRequest) {
  const callbackUrl = new URL("/api/v1/auth/google/callback", normalizedApiBaseUrl());
  forwardSearchParam(request, callbackUrl, "code");
  forwardSearchParam(request, callbackUrl, "state");
  forwardSearchParam(request, callbackUrl, "error");
  forwardSearchParam(request, callbackUrl, "error_description");

  try {
    const cookieHeader = request.headers.get("cookie");
    const backendResponse = await fetch(callbackUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(cookieHeader ? { Cookie: cookieHeader } : {})
      },
      cache: "no-store"
    });

    if (!backendResponse.ok) {
      return redirectToLogin(request, await readGoogleOAuthErrorCode(backendResponse));
    }

    await readCallbackPayload(backendResponse);
    const response = NextResponse.redirect(createPublicUrl(request, "/dashboard"));
    appendSetCookieHeaders(response, backendResponse);
    response.headers.set("cache-control", "no-store");
    return response;
  } catch {
    return redirectToLogin(request, "google-oauth-unavailable");
  }
}

function forwardSearchParam(request: NextRequest, destination: URL, name: string) {
  const value = request.nextUrl.searchParams.get(name);
  if (value) {
    destination.searchParams.set(name, value);
  }
}

async function readCallbackPayload(
  response: Response,
): Promise<GoogleOAuthCallbackResponse | null> {
  try {
    const payload = (await response.json()) as GoogleOAuthCallbackResponse;
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

async function readGoogleOAuthErrorCode(response: Response) {
  try {
    const payload = await response.json();
    const code = extractErrorCode(payload);
    return code && LOGIN_ERROR_CODES.has(code) ? code : "google-oauth-unavailable";
  } catch {
    return "google-oauth-unavailable";
  }
}

function extractErrorCode(payload: unknown) {
  if (!isRecord(payload)) {
    return null;
  }

  const detail = payload.detail;
  if (isRecord(detail) && typeof detail.code === "string") {
    return detail.code;
  }

  return typeof payload.code === "string" ? payload.code : null;
}

function appendSetCookieHeaders(response: NextResponse, backendResponse: Response) {
  const headers = backendResponse.headers as Headers & { getSetCookie?: () => string[] };
  const setCookieHeaders =
    typeof headers.getSetCookie === "function" ? headers.getSetCookie() : [];

  if (setCookieHeaders.length > 0) {
    for (const setCookie of setCookieHeaders) {
      response.headers.append("set-cookie", setCookie);
    }
    return;
  }

  const setCookie = backendResponse.headers.get("set-cookie");
  if (setCookie) {
    response.headers.append("set-cookie", setCookie);
  }
}

function redirectToLogin(request: NextRequest, errorCode: string) {
  const loginUrl = createPublicUrl(request, "/login");
  loginUrl.searchParams.set(
    "error",
    LOGIN_ERROR_CODES.has(errorCode) ? errorCode : "google-oauth-unavailable",
  );
  const response = NextResponse.redirect(loginUrl);
  response.headers.set("cache-control", "no-store");
  return response;
}

function normalizedApiBaseUrl() {
  return API_BASE_URL.replace(/\/$/, "");
}

function resolveApiBaseUrl() {
  const configuredApiBaseUrl = process.env.API_BASE_URL?.trim();
  const normalizedApiBaseUrl = (configuredApiBaseUrl || defaultApiBaseUrl()).replace(/\/$/, "");

  if (
    isVercelProductionTarget() &&
    isParserlyImmutableDeploymentUrl(normalizedApiBaseUrl)
  ) {
    return CANONICAL_API_BASE_URL;
  }

  return normalizedApiBaseUrl;
}

function defaultApiBaseUrl() {
  return isVercelProductionTarget() ? CANONICAL_API_BASE_URL : LOCAL_API_BASE_URL;
}

function isVercelProductionTarget() {
  return process.env.VERCEL_ENV === "production" || process.env.VERCEL_TARGET_ENV === "production";
}

function isParserlyImmutableDeploymentUrl(url: string) {
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    return false;
  }

  if (parsedUrl.protocol !== "https:") {
    return false;
  }

  if (!parsedUrl.hostname.startsWith(PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX)) {
    return false;
  }

  if (!parsedUrl.hostname.endsWith(VERCEL_TEAM_HOST_SUFFIX)) {
    return false;
  }

  const deploymentId = parsedUrl.hostname
    .replace(PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX, "")
    .replace(VERCEL_TEAM_HOST_SUFFIX, "");
  return /^[a-z0-9]+$/.test(deploymentId);
}

function createPublicUrl(request: NextRequest, pathname: string) {
  if (isVercelProductionTarget()) {
    return new URL(pathname, CANONICAL_APP_BASE_URL);
  }

  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = forwardedHost ?? request.headers.get("host");

  if (!host) {
    return new URL(pathname, request.url);
  }

  const protocol =
    request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(/:$/, "");

  return new URL(pathname, `${protocol}://${host}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
