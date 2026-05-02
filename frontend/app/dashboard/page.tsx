import { cookies } from "next/headers";
import { DashboardClient } from "@/components/dashboard/dashboard-client";

interface DashboardPageProps {
  searchParams?: {
    payment?: string | string[];
  };
}

export default function DashboardPage({ searchParams }: DashboardPageProps) {
  const authCookieName = process.env.AUTH_COOKIE_NAME ?? "access_token";
  const isAuthenticated = Boolean(cookies().get(authCookieName)?.value);
  const paymentParam = Array.isArray(searchParams?.payment)
    ? searchParams?.payment[0]
    : searchParams?.payment;

  return (
    <DashboardClient
      isAuthenticated={isAuthenticated}
      paymentRequired={isAuthenticated && paymentParam === "required"}
    />
  );
}
