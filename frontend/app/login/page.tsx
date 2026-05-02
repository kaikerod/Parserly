import type { Metadata } from "next";
import { LoginClient } from "@/components/auth/login-client";

export const metadata: Metadata = {
  title: "Login | Parserly",
  description: "Acesse o Parserly por magic link para analisar currículos."
};

interface LoginPageProps {
  searchParams?: {
    error?: string | string[];
    reason?: string | string[];
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
  const reasonCode = Array.isArray(searchParams?.reason)
    ? searchParams?.reason[0]
    : searchParams?.reason;
  const initialNotice =
    reasonCode === "free-limit"
      ? "Você usou as 3 análises grátis. Cadastre seu e-mail para acessar o pagamento via PIX."
      : undefined;

  return (
    <LoginClient
      initialError={errorCode ? LOGIN_ERROR_MESSAGES[errorCode] : undefined}
      initialNotice={initialNotice}
    />
  );
}
