const LOCAL_API_BASE_URL = "http://localhost:8000";
const CANONICAL_API_BASE_URL = "https://parserly-api.vercel.app";
const PARSERLY_IMMUTABLE_DEPLOYMENT_PREFIX = "parserly-";
const VERCEL_TEAM_HOST_SUFFIX = "-kaikerods-projects.vercel.app";
const apiBaseUrl = resolveApiBaseUrl();

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

function isParserlyImmutableDeploymentUrl(url) {
  let parsedUrl;
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

const immutablePublicAssetCacheHeaders = [
  {
    key: "Cache-Control",
    value: "public, max-age=31536000, immutable"
  }
];

const publicPageCacheHeaders = [
  {
    key: "Cache-Control",
    value: "public, max-age=0, s-maxage=300, stale-while-revalidate=3600"
  }
];

const noStoreHeaders = [
  {
    key: "Cache-Control",
    value: "no-store, max-age=0"
  }
];

const securityHeaders = [
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains; preload"
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff"
  },
  {
    key: "X-Frame-Options",
    value: "DENY"
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin"
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()"
  }
];

const apiRewriteRules = [
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

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return apiRewriteRules;
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders
      },
      {
        source: "/icon.svg",
        headers: immutablePublicAssetCacheHeaders
      },
      {
        source: "/login",
        headers: publicPageCacheHeaders
      },
      {
        source: "/privacidade",
        headers: publicPageCacheHeaders
      },
      {
        source: "/dashboard",
        headers: noStoreHeaders
      },
      {
        source: "/auth/verify",
        headers: noStoreHeaders
      },
      {
        source: "/auth/google/callback",
        headers: noStoreHeaders
      },
      {
        source: "/api/v1/:path*",
        headers: noStoreHeaders
      }
    ];
  }
};

export default nextConfig;
