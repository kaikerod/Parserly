import { cookies } from "next/headers";
import { DashboardClient } from "@/components/dashboard/dashboard-client";

interface DashboardPageProps {
  searchParams?: Promise<{
    payment?: string | string[];
  }>;
}

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const authCookieName = process.env.AUTH_COOKIE_NAME ?? "access_token";
  const cookieStore = await cookies();
  const resolvedSearchParams = await searchParams;
  const isAuthenticated = Boolean(cookieStore.get(authCookieName)?.value);
  const paymentParam = Array.isArray(resolvedSearchParams?.payment)
    ? resolvedSearchParams?.payment[0]
    : resolvedSearchParams?.payment;

  return (
    <DashboardClient
      isAuthenticated={isAuthenticated}
      paymentRequired={isAuthenticated && paymentParam === "required"}
    />
  );
}
