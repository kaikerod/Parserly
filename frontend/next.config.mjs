const LOCAL_API_BASE_URL = "http://localhost:8000";
const apiBaseUrl = (process.env.API_BASE_URL ?? LOCAL_API_BASE_URL).replace(/\/$/, "");

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
