const LOCAL_API_BASE_URL = "http://localhost:8000";
const CANONICAL_API_BASE_URL = "https://parserly-api.vercel.app";
const apiBaseUrl = resolveApiBaseUrl();

function resolveApiBaseUrl() {
  const configuredApiBaseUrl = process.env.API_BASE_URL?.trim();
  const normalizedApiBaseUrl = (configuredApiBaseUrl || defaultApiBaseUrl()).replace(/\/$/, "");

  if (
    process.env.VERCEL_ENV === "production" &&
    isParserlyImmutableDeploymentUrl(normalizedApiBaseUrl)
  ) {
    return CANONICAL_API_BASE_URL;
  }

  return normalizedApiBaseUrl;
}

function defaultApiBaseUrl() {
  return process.env.VERCEL_ENV === "production" ? CANONICAL_API_BASE_URL : LOCAL_API_BASE_URL;
}

function isParserlyImmutableDeploymentUrl(url) {
  if (!url.startsWith("https://parserly-")) {
    return false;
  }

  if (!url.endsWith("-kaikerods-projects.vercel.app")) {
    return false;
  }

  const deploymentId = url
    .replace("https://parserly-", "")
    .replace("-kaikerods-projects.vercel.app", "");
  return /^[a-z0-9]+$/.test(deploymentId);
}

const immutableAssetCacheHeaders = [
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

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBaseUrl}/api/v1/:path*`
      }
    ];
  },
  async headers() {
    return [
      {
        source: "/_next/static/:path*",
        headers: immutableAssetCacheHeaders
      },
      {
        source: "/icon.svg",
        headers: immutableAssetCacheHeaders
      },
      {
        source: "/login",
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
        source: "/api/v1/:path*",
        headers: noStoreHeaders
      }
    ];
  }
};

export default nextConfig;
