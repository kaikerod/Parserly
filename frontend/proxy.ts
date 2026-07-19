import { NextRequest, NextResponse } from "next/server";

const CANONICAL_APP_ORIGIN = "https://www.parserly.com.br";
const CANONICAL_APP_HOSTNAME = "www.parserly.com.br";
const LEGACY_APP_HOSTNAMES = new Set([
  "parserly.com.br",
  "parserly.vercel.app",
  "parserly-web.vercel.app"
]);
const PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX = "parserly-";
const VERCEL_TEAM_HOST_SUFFIX = "-kaikerods-projects.vercel.app";

export function proxy(request: NextRequest) {
  if (!isVercelProductionTarget()) {
    return NextResponse.next();
  }

  const hostname = request.nextUrl.hostname.toLowerCase();
  if (!shouldRedirectToCanonicalHost(hostname)) {
    return NextResponse.next();
  }

  const canonicalUrl = new URL(request.nextUrl.pathname, CANONICAL_APP_ORIGIN);
  canonicalUrl.search = request.nextUrl.search;
  return NextResponse.redirect(canonicalUrl, 307);
}

export const config = {
  matcher: [
    "/login",
    "/cadastro",
    "/auth/verify",
    "/auth/google/callback",
    "/api/v1/auth/google/start"
  ]
};

function shouldRedirectToCanonicalHost(hostname: string) {
  if (hostname === CANONICAL_APP_HOSTNAME) {
    return false;
  }

  return LEGACY_APP_HOSTNAMES.has(hostname) || isParserlyImmutableDeploymentHost(hostname);
}

function isVercelProductionTarget() {
  return process.env.VERCEL_ENV === "production" || process.env.VERCEL_TARGET_ENV === "production";
}

function isParserlyImmutableDeploymentHost(hostname: string) {
  if (!hostname.startsWith(PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX)) {
    return false;
  }

  return hostname.endsWith(VERCEL_TEAM_HOST_SUFFIX);
}
