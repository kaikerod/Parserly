const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBaseUrl.replace(/\/$/, "")}/api/v1/:path*`
      }
    ];
  }
};

export default nextConfig;
