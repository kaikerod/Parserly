import type { Metadata } from "next";
import { LoginClient } from "@/components/auth/login-client";

export const metadata: Metadata = {
  title: "Login | Parserly",
  description: "Entre ou crie acesso no Parserly por magic link usando seu e-mail."
};

interface LoginPageProps {
  searchParams?: Promise<{
    error?: string | string[];
    reason?: string | string[];
    intent?: string | string[];
  }>;
}

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  "missing-token": "O link de acesso não contém um token válido.",
  "invalid-link": "Este link expirou ou já foi usado. Solicite um novo acesso.",
  "account-not-found": "Solicite um novo link de acesso para continuar.",
  "verify-unavailable": "Não foi possível verificar o link agora. Tente novamente em instantes.",
  "google-oauth-invalid-state": "Nao foi possivel confirmar o login com Google. Tente novamente.",
  "google-oauth-denied": "O acesso pelo Google nao foi concluido.",
  "google-email-unverified": "O Google nao confirmou este e-mail. Use o magic link.",
  "google-account-conflict": "Esta conta Google ja esta vinculada a outro acesso Parserly.",
  "google-oauth-unavailable": "Nao foi possivel entrar com Google agora. Tente novamente em instantes."
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const resolvedSearchParams = await searchParams;
  const errorCode = Array.isArray(resolvedSearchParams?.error)
    ? resolvedSearchParams?.error[0]
    : resolvedSearchParams?.error;
  const reasonCode = Array.isArray(resolvedSearchParams?.reason)
    ? resolvedSearchParams?.reason[0]
    : resolvedSearchParams?.reason;
  const intentCode = Array.isArray(resolvedSearchParams?.intent)
    ? resolvedSearchParams?.intent[0]
    : resolvedSearchParams?.intent;
  const isRegistrationIntent = intentCode === "registration" || reasonCode === "free-limit";
  const initialNotice =
    isRegistrationIntent
      ? "Você atingiu o limite gratuito. Cadastre seu e-mail para continuar pelo checkout PIX."
      : undefined;

  return (
    <LoginClient
      initialError={errorCode ? LOGIN_ERROR_MESSAGES[errorCode] : undefined}
      initialNotice={initialNotice}
      intent={isRegistrationIntent ? "registration" : "login"}
    />
  );
}
