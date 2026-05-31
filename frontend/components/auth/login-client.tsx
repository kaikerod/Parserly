"use client";

import { type FormEvent, type MouseEvent, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Copy,
  FileSearch,
  Loader2,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserCheck
} from "lucide-react";
import { ApiError, googleOAuthStartPath, requestMagicLink } from "@/lib/api";

type LoginPhase = "idle" | "submitting" | "sent" | "error";
type LoginIntent = "login" | "registration";

interface LoginClientProps {
  initialError?: string;
  initialNotice?: string;
  intent?: LoginIntent;
}

const LOGIN_MARKERS = [
  { label: "Acesso", value: "Google" },
  { label: "Alternativa", value: "link por e-mail" },
  { label: "Sessão", value: "7 dias" }
];

const REGISTRATION_MARKERS = [
  { label: "Cadastro", value: "Google" },
  { label: "Alternativa", value: "link por e-mail" },
  { label: "Checkout", value: "PIX" }
];

export function LoginClient({
  initialError,
  initialNotice,
  intent = "login"
}: LoginClientProps) {
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<LoginPhase>(initialError ? "error" : "idle");
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [magicLink, setMagicLink] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");
  const [hasAcceptedPrivacy, setHasAcceptedPrivacy] = useState(false);
  const [privacyError, setPrivacyError] = useState<string | null>(null);

  const normalizedEmail = useMemo(() => email.trim().toLowerCase(), [email]);
  const isSubmitting = phase === "submitting";
  const emailDescriptionId = error ? "email-help login-error" : "email-help";
  const isRegistrationFlow = intent === "registration";
  const markers = isRegistrationFlow ? REGISTRATION_MARKERS : LOGIN_MARKERS;
  const googleButtonLabel = isRegistrationFlow ? "Cadastrar com Google" : "Continuar com Google";
  const isRegistrationActionDisabled = isRegistrationFlow && !hasAcceptedPrivacy;
  const privacyDescriptionId = privacyError
    ? "privacy-agreement-help privacy-agreement-error"
    : "privacy-agreement-help";
  const submitButtonClassName = [
    "focus-ring inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md px-5 py-3 text-sm font-bold transition disabled:cursor-not-allowed",
    isRegistrationActionDisabled
      ? "bg-fog text-paper/45"
      : "bg-acid text-ink hover:bg-mint motion-safe:hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-70"
  ].join(" ");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!ensurePrivacyAccepted()) {
      return;
    }

    if (!isValidEmail(normalizedEmail)) {
      setPhase("error");
      setError("Informe um e-mail válido para receber o link de acesso.");
      return;
    }

    setPhase("submitting");
    setError(null);
    setMagicLink(null);
    setCopyState("idle");

    try {
      const response = await requestMagicLink(normalizedEmail);
      setSentTo(normalizedEmail);
      setMagicLink(response.magic_link ?? null);
      setPhase("sent");
    } catch (requestError) {
      setPhase("error");
      setError(resolveLoginError(requestError));
    }
  }

  function handleGoogleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (!ensurePrivacyAccepted()) {
      event.preventDefault();
    }
  }

  function handlePrivacyChange(accepted: boolean) {
    setHasAcceptedPrivacy(accepted);

    if (accepted) {
      setPrivacyError(null);
    }
  }

  function ensurePrivacyAccepted() {
    if (!isRegistrationFlow || hasAcceptedPrivacy) {
      return true;
    }

    setPrivacyError("Para criar sua conta, aceite a Política de Privacidade.");
    return false;
  }

  function handleEmailChange(value: string) {
    setEmail(value);

    if (phase === "sent") {
      setPhase("idle");
      setSentTo(null);
      setMagicLink(null);
      setCopyState("idle");
    }

    if (phase === "error") {
      setPhase("idle");
      setError(null);
    }
  }

  async function handleCopyMagicLink() {
    if (!magicLink) {
      return;
    }

    try {
      await navigator.clipboard.writeText(magicLink);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setError("Não foi possível copiar automaticamente. Abra o link local abaixo.");
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-5 text-paper sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-7xl flex-col gap-7">
        <nav className="flex flex-wrap items-center justify-between gap-3 border-b border-line/55 pb-4 text-xs text-paper/60">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-violet text-paper shadow-glow">
              <FileSearch className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="flex min-w-0 items-center gap-3">
              <span className="font-display text-base font-semibold text-paper">Parserly</span>
              <span className="hidden text-paper/30 sm:inline">/</span>
              <span className="hidden truncate sm:inline">
                {isRegistrationFlow
                  ? "Cadastro com Google ou link por e-mail"
                  : "Login com Google ou link por e-mail"}
              </span>
            </div>
          </div>

          <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:justify-end">
            <a
              href="/privacidade"
              className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 font-semibold text-paper/75 transition hover:border-acid/45 hover:bg-fog"
            >
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Privacidade
            </a>
            <span className="hidden text-paper/75 sm:inline">Análise ATS para currículos</span>
          </div>
        </nav>

        <section className="grid flex-1 items-center gap-6 pb-5 lg:grid-cols-[1fr_29rem]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-md border border-line/70 bg-graphite/90 px-3 py-1.5 text-xs font-bold text-paper/70">
              {isRegistrationFlow ? (
                <LockKeyhole className="h-4 w-4 text-acid" aria-hidden="true" />
              ) : (
                <UserCheck className="h-4 w-4 text-acid" aria-hidden="true" />
              )}
              {isRegistrationFlow ? "Conta protegida" : "Acesso seguro"}
            </div>

            <h1 className="mt-5 max-w-4xl text-balance font-display text-4xl font-semibold leading-none text-paper md:text-5xl">
              {isRegistrationFlow ? "Crie seu acesso." : "Acesse sua conta."}
              <br />
              Continue sua <span className="text-lavender">análise.</span>
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-6 text-paper/70">
              {isRegistrationFlow
                ? "Use Google para criar sua conta rapidamente ou receba um link por e-mail para preservar sua quota e continuar sem senha."
                : "Entre com Google ou receba um link por e-mail para manter sua quota e continuar suas análises sem senha."}
            </p>

            <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
              {markers.map((marker) => (
                <div
                  key={marker.label}
                  className="rounded-md border border-line/70 bg-graphite/90 p-4"
                >
                  <p className="text-xs font-semibold text-paper/60">{marker.label}</p>
                  <p className="mt-2 font-display text-2xl font-semibold text-copper">
                    {marker.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <section
            aria-labelledby="login-title"
            className="rounded-md border border-line/75 bg-graphite/95 p-5 sm:p-6"
          >
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold text-acid">
                  {isRegistrationFlow ? "Identificação segura" : "Acesso sem senha"}
                </p>
                <h2 id="login-title" className="mt-1 font-display text-3xl font-semibold">
                  {isRegistrationFlow ? "Criar acesso" : "Entrar no Parserly"}
                </h2>
              </div>
              <ShieldCheck className="h-6 w-6 text-teal" aria-hidden="true" />
            </div>

            {initialNotice ? (
              <div
                className="mb-5 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper"
                role="status"
              >
                <div className="flex items-start gap-3">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
                  <p className="leading-6 text-paper/75">{initialNotice}</p>
                </div>
              </div>
            ) : null}

            {isRegistrationFlow ? (
              <div className="mb-5 rounded-md border border-line/70 bg-night/85 p-4">
                <label
                  htmlFor="privacy-agreement"
                  className="flex cursor-pointer items-start gap-3 text-sm leading-6 text-paper/80"
                >
                  <input
                    id="privacy-agreement"
                    type="checkbox"
                    checked={hasAcceptedPrivacy}
                    onChange={(event) => handlePrivacyChange(event.target.checked)}
                    aria-describedby={privacyDescriptionId}
                    className="focus-ring mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-line/80 bg-graphite accent-acid"
                  />
                  <span>
                    Li e concordo com os termos da{" "}
                    <a
                      href="/privacidade"
                      onClick={(event) => event.stopPropagation()}
                      className="focus-ring rounded-sm font-semibold text-acid underline decoration-acid/50 underline-offset-4"
                    >
                      Política de Privacidade
                    </a>{" "}
                    do Parserly.
                  </span>
                </label>
                <p id="privacy-agreement-help" className="mt-2 pl-7 text-xs leading-5 text-paper/60">
                  O aceite é obrigatório para criar uma conta com Google ou link por e-mail.
                </p>
                {privacyError ? (
                  <p
                    id="privacy-agreement-error"
                    className="mt-2 pl-7 text-xs font-semibold leading-5 text-coral"
                  >
                    {privacyError}
                  </p>
                ) : null}
              </div>
            ) : null}

            <a
              href={googleOAuthStartPath()}
              onClick={handleGoogleClick}
              aria-disabled={isRegistrationActionDisabled}
              aria-describedby={isRegistrationFlow ? "privacy-agreement-help" : undefined}
              className={`focus-ring mb-5 inline-flex min-h-12 w-full items-center justify-center gap-3 rounded-md border border-paper bg-paper px-5 py-3 text-sm font-bold text-ink transition hover:bg-white ${
                isRegistrationActionDisabled
                  ? "cursor-not-allowed opacity-60"
                  : "motion-safe:hover:-translate-y-0.5"
              }`}
            >
              <svg
                className="h-5 w-5 shrink-0"
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M21.35 11.1H12v2.9h5.35c-.25 1.4-1.02 2.58-2.2 3.38v2.8h3.56c2.08-1.92 3.28-4.75 3.28-8.08 0-.76-.07-1.49-.22-2.2Z"
                  fill="#4285F4"
                />
                <path
                  d="M12 22c2.97 0 5.46-.98 7.28-2.66l-3.56-2.8c-.98.66-2.24 1.05-3.72 1.05-2.86 0-5.29-1.93-6.16-4.53H2.14v2.9A9.99 9.99 0 0 0 12 22Z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 13.06A5.99 5.99 0 0 1 5.5 11c0-.72.12-1.42.34-2.06v-2.9H2.14A9.99 9.99 0 0 0 2 11c0 1.61.39 3.12 1.08 4.44l2.76-2.38Z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.94c1.62 0 3.07.56 4.21 1.66l3.16-3.16C17.44 2.68 14.97 1.7 12 1.7A9.99 9.99 0 0 0 2.14 8.04l3.7 2.9C6.71 7.86 9.14 5.94 12 5.94Z"
                  fill="#EA4335"
                />
              </svg>
              {googleButtonLabel}
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </a>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="email" className="text-sm font-semibold text-paper/80">
                  E-mail
                </label>
                <div className="relative mt-2">
                  <Mail
                    className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-paper/35"
                    aria-hidden="true"
                  />
                  <input
                    id="email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => handleEmailChange(event.target.value)}
                    disabled={isSubmitting}
                    className="focus-ring min-h-12 w-full rounded-md border border-line/80 bg-night py-3 pl-11 pr-4 text-sm text-paper placeholder:text-paper/60 transition hover:border-acid/45 disabled:cursor-not-allowed disabled:opacity-70"
                    placeholder="voce@empresa.com"
                    aria-describedby={emailDescriptionId}
                  />
                </div>
                <p id="email-help" className="mt-2 text-xs leading-5 text-paper/60">
                  {isRegistrationFlow
                    ? "Se o e-mail já tiver acesso, ele será usado para recuperar sua sessão."
                    : "Se for seu primeiro acesso, o Parserly cria sua conta ao verificar o link."}
                </p>
              </div>

              <button
                type="submit"
                disabled={isSubmitting || isRegistrationActionDisabled}
                className={submitButtonClassName}
              >
                {isSubmitting ? (
                  <Loader2
                    className="h-5 w-5 animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                ) : (
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                )}
                {isSubmitting
                  ? "Enviando link..."
                  : isRegistrationFlow
                    ? "Enviar link de acesso"
                    : "Receber link por e-mail"}
              </button>
            </form>

            {phase === "sent" ? (
              <div
                className="mt-5 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper"
                role="status"
                aria-live="polite"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
                  <div>
                    <p className="font-semibold">Verifique o e-mail {sentTo}.</p>
                    <p className="mt-1 leading-6 text-paper/65">
                      {isRegistrationFlow
                        ? "O link chega em instantes, expira em 15 minutos e só pode ser usado uma vez."
                        : "O link de acesso chega em instantes, expira em 15 minutos e só pode ser usado uma vez."}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            {magicLink ? (
              <div className="mt-4 rounded-md border border-line/70 bg-night p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold text-paper/60">Link local</p>
                  <button
                    type="button"
                    onClick={handleCopyMagicLink}
                    className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-graphite px-3 py-2 text-xs font-semibold text-paper transition hover:border-acid/45 hover:bg-fog"
                  >
                    {copyState === "copied" ? (
                      <CheckCircle2 className="h-4 w-4 text-acid" aria-hidden="true" />
                    ) : (
                      <Copy className="h-4 w-4" aria-hidden="true" />
                    )}
                    {copyState === "copied" ? "Copiado" : "Copiar"}
                  </button>
                </div>
                <a
                  href={magicLink}
                  className="focus-ring mt-3 block truncate rounded-md border border-line/70 bg-graphite px-3 py-2 font-mono text-xs text-lavender transition hover:border-acid/45 hover:text-acid"
                >
                  {magicLink}
                </a>
              </div>
            ) : null}

            {error ? (
              <div
                id="login-error"
                className="mt-5 flex items-start gap-3 rounded-md border border-coral/35 bg-coral/10 px-4 py-3 text-sm text-paper"
                role="alert"
              >
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden="true" />
                <p>{error}</p>
              </div>
            ) : null}

            <div className="mt-6 flex items-start gap-3 border-t border-line/65 pt-5 text-sm text-paper/65">
              <Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-copper" aria-hidden="true" />
              <p>Solicitações são limitadas por e-mail para proteger o acesso.</p>
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function resolveLoginError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const retryAfter = error.retryAfter ? formatRetryAfter(error.retryAfter) : "alguns minutos";
      return `Muitas solicitações para este e-mail. Tente novamente em ${retryAfter}.`;
    }

    if (error.status === 422) {
      return "Informe um e-mail válido para receber o link de acesso.";
    }

    return error.message;
  }

  return error instanceof Error ? error.message : "Não foi possível enviar o link de acesso.";
}

function formatRetryAfter(totalSeconds: number) {
  if (totalSeconds < 60) {
    return `${totalSeconds} segundos`;
  }

  const minutes = Math.ceil(totalSeconds / 60);
  return `${minutes} min`;
}
