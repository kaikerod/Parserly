import type { Metadata } from "next";
import { LoginClient } from "@/components/auth/login-client";

export const metadata: Metadata = {
  title: "Login | Parserly",
  description: "Acesse o Parserly por magic link para analisar currículos."
};

interface LoginPageProps {
  searchParams?: {
    error?: string | string[];
  };
}

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  "missing-token": "O link de acesso não contém um token válido.",
  "invalid-link": "Este link expirou ou já foi usado. Solicite um novo acesso.",
  "verify-unavailable": "Não foi possível verificar o link agora. Tente novamente em instantes."
};

export default function LoginPage({ searchParams }: LoginPageProps) {
  const errorCode = Array.isArray(searchParams?.error)
    ? searchParams?.error[0]
    : searchParams?.error;

  return <LoginClient initialError={errorCode ? LOGIN_ERROR_MESSAGES[errorCode] : undefined} />;
}
