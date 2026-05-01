import { cookies } from "next/headers";
import { DashboardClient } from "@/components/dashboard/dashboard-client";

export default function DashboardPage() {
  const authCookieName = process.env.AUTH_COOKIE_NAME ?? "access_token";
  const isAuthenticated = Boolean(cookies().get(authCookieName)?.value);

  return <DashboardClient isAuthenticated={isAuthenticated} />;
}
