import { NextRequest, NextResponse } from "next/server";

const LOCAL_API_BASE_URL = "http://localhost:8000";
const CANONICAL_API_BASE_URL = "https://parserly-api.vercel.app";
const PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX = "parserly-";
const VERCEL_TEAM_HOST_SUFFIX = "-kaikerods-projects.vercel.app";
const API_BASE_URL = resolveApiBaseUrl();

export const dynamic = "force-dynamic";

interface VerifyMagicLinkPayload {
  requires_payment?: boolean;
}

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");

  if (!token) {
    return redirectToLogin(request, "missing-token");
  }

  const verifyUrl = new URL("/api/v1/auth/verify", normalizedApiBaseUrl());
  verifyUrl.searchParams.set("token", token);

  try {
    const cookieHeader = request.headers.get("cookie");
    const backendResponse = await fetch(verifyUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(cookieHeader ? { Cookie: cookieHeader } : {})
      },
      cache: "no-store"
    });

    if (!backendResponse.ok) {
      return redirectToLogin(
        request,
        isInvalidMagicLinkStatus(backendResponse.status) ? "invalid-link" : "verify-unavailable"
      );
    }

    const payload = await readVerifyPayload(backendResponse);
    const dashboardPath = payload?.requires_payment
      ? "/dashboard?payment=required"
      : "/dashboard";
    const response = NextResponse.redirect(createPublicUrl(request, dashboardPath));
    const setCookie = backendResponse.headers.get("set-cookie");

    if (setCookie) {
      response.headers.append("set-cookie", setCookie);
    }

    response.headers.set("cache-control", "no-store");
    return response;
  } catch {
    return redirectToLogin(request, "verify-unavailable");
  }
}

async function readVerifyPayload(response: Response): Promise<VerifyMagicLinkPayload | null> {
  try {
    const payload = (await response.json()) as VerifyMagicLinkPayload;
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

function redirectToLogin(request: NextRequest, reason: string) {
  const loginUrl = createPublicUrl(request, "/login");
  loginUrl.searchParams.set("error", reason);
  return NextResponse.redirect(loginUrl);
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

function isInvalidMagicLinkStatus(statusCode: number) {
  return [400, 401, 404, 410, 422].includes(statusCode);
}

function createPublicUrl(request: NextRequest, pathname: string) {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = forwardedHost ?? request.headers.get("host");

  if (!host) {
    return new URL(pathname, request.url);
  }

  const protocol =
    request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(/:$/, "");

  return new URL(pathname, `${protocol}://${host}`);
}
