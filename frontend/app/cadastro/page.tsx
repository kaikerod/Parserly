import type { Metadata } from "next";
import { LoginClient } from "@/components/auth/login-client";

export const metadata: Metadata = {
  title: "Criar acesso | Parserly",
  description: "Crie seu acesso ao Parserly com Google ou magic link."
};

interface RegistrationPageProps {
  searchParams?: Promise<{
    reason?: string | string[];
  }>;
}

export default async function RegistrationPage({ searchParams }: RegistrationPageProps) {
  const resolvedSearchParams = await searchParams;
  const reasonCode = Array.isArray(resolvedSearchParams?.reason)
    ? resolvedSearchParams?.reason[0]
    : resolvedSearchParams?.reason;
  const isFreeLimitReason = reasonCode === "free-limit";

  return (
    <LoginClient
      initialNotice={
        isFreeLimitReason
          ? "Você atingiu o limite gratuito. Crie seu acesso para continuar."
          : undefined
      }
      intent="registration"
    />
  );
}
