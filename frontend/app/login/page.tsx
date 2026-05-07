import type { Metadata } from "next";
import { LoginClient } from "@/components/auth/login-client";

export const metadata: Metadata = {
  title: "Login | Parserly",
  description: "Acesse sua conta Parserly por magic link usando o e-mail já cadastrado."
};

interface LoginPageProps {
  searchParams?: {
    error?: string | string[];
    reason?: string | string[];
    intent?: string | string[];
  };
}

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  "missing-token": "O link de acesso não contém um token válido.",
  "invalid-link": "Este link expirou ou já foi usado. Solicite um novo acesso.",
  "account-not-found": "Use o e-mail já cadastrado no Parserly para solicitar um novo link.",
  "verify-unavailable": "Não foi possível verificar o link agora. Tente novamente em instantes."
};

export default function LoginPage({ searchParams }: LoginPageProps) {
  const errorCode = Array.isArray(searchParams?.error)
    ? searchParams?.error[0]
    : searchParams?.error;
  const reasonCode = Array.isArray(searchParams?.reason)
    ? searchParams?.reason[0]
    : searchParams?.reason;
  const intentCode = Array.isArray(searchParams?.intent)
    ? searchParams?.intent[0]
    : searchParams?.intent;
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
