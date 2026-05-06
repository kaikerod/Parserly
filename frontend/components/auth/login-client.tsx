"use client";

import { FormEvent, useMemo, useState } from "react";
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
import { ApiError, requestMagicLink } from "@/lib/api";

type LoginPhase = "idle" | "submitting" | "sent" | "error";
type LoginIntent = "login" | "registration";

interface LoginClientProps {
  initialError?: string;
  initialNotice?: string;
  intent?: LoginIntent;
}

const LOGIN_MARKERS = [
  { label: "Conta", value: "existente" },
  { label: "Link", value: "15 min" },
  { label: "Sessão", value: "7 dias" }
];

const REGISTRATION_MARKERS = [
  { label: "Cadastro", value: "sem senha" },
  { label: "Link", value: "15 min" },
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

  const normalizedEmail = useMemo(() => email.trim().toLowerCase(), [email]);
  const isSubmitting = phase === "submitting";
  const emailDescriptionId = error ? "email-help login-error" : "email-help";
  const isRegistrationFlow = intent === "registration";
  const markers = isRegistrationFlow ? REGISTRATION_MARKERS : LOGIN_MARKERS;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

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
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 bg-[linear-gradient(115deg,rgba(109,93,252,0.24),transparent_44%),linear-gradient(250deg,rgba(69,255,115,0.14),transparent_38%)]" />

      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-7xl flex-col gap-7">
        <nav className="flex items-center justify-between border-b border-line/55 pb-4 text-xs text-paper/60">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-violet text-paper shadow-glow">
              <FileSearch className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="flex min-w-0 items-center gap-3">
              <span className="font-display text-base font-semibold text-paper">Parserly</span>
              <span className="hidden text-paper/30 sm:inline">/</span>
              <span className="hidden truncate sm:inline">
                {isRegistrationFlow ? "Cadastro por magic link" : "Login de usuário cadastrado"}
              </span>
            </div>
          </div>

          <span className="hidden text-paper/75 sm:inline">Análise ATS para currículos</span>
        </nav>

        <section className="grid flex-1 items-center gap-6 pb-5 lg:grid-cols-[1fr_29rem]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-md border border-line/70 bg-graphite/80 px-3 py-1.5 text-xs font-bold uppercase text-paper/70 shadow-tool backdrop-blur">
              {isRegistrationFlow ? (
                <LockKeyhole className="h-4 w-4 text-acid" aria-hidden="true" />
              ) : (
                <UserCheck className="h-4 w-4 text-acid" aria-hidden="true" />
              )}
              {isRegistrationFlow ? "Cadastro por e-mail" : "Conta existente"}
            </div>

            <h1 className="mt-5 max-w-4xl font-display text-5xl font-semibold leading-none text-paper md:text-6xl">
              {isRegistrationFlow ? "Crie seu acesso." : "Acesse sua conta."}
              <br />
              Continue sua <span className="accent-text">análise.</span>
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-6 text-paper/65">
              {isRegistrationFlow
                ? "Use seu e-mail para identificar sua conta, preservar sua quota e continuar sem senha."
                : "Use o e-mail já cadastrado para recuperar sua sessão, manter sua quota e continuar suas análises sem senha."}
            </p>

            <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
              {markers.map((marker) => (
                <div
                  key={marker.label}
                  className="rounded-md border border-line/70 bg-graphite/80 p-4 shadow-tool backdrop-blur"
                >
                  <p className="text-xs font-semibold uppercase text-paper/45">{marker.label}</p>
                  <p className="mt-2 font-display text-2xl font-semibold text-copper">
                    {marker.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <section
            aria-labelledby="login-title"
            className="rounded-md border border-line/75 bg-graphite/90 p-5 shadow-panel backdrop-blur sm:p-6"
          >
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase text-acid">
                  {isRegistrationFlow ? "Identificação" : "Conta cadastrada"}
                </p>
                <h2 id="login-title" className="mt-1 font-display text-3xl font-semibold">
                  {isRegistrationFlow ? "Receber magic link" : "Entrar no Parserly"}
                </h2>
              </div>
              <ShieldCheck className="h-6 w-6 text-teal" aria-hidden="true" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="email" className="text-sm font-semibold text-paper/80">
                  {isRegistrationFlow ? "E-mail" : "E-mail cadastrado"}
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
                    onChange={(event) => setEmail(event.target.value)}
                    disabled={isSubmitting}
                    className="focus-ring min-h-12 w-full rounded-md border border-line/80 bg-night py-3 pl-11 pr-4 text-sm text-paper placeholder:text-paper/30 transition hover:border-acid/45 disabled:cursor-not-allowed disabled:opacity-70"
                    placeholder="voce@empresa.com"
                    aria-describedby={emailDescriptionId}
                  />
                </div>
                <p id="email-help" className="mt-2 text-xs leading-5 text-paper/45">
                  {isRegistrationFlow
                    ? "Se o e-mail já existir, ele será usado para recuperar sua conta."
                    : "O acesso é enviado somente para e-mails com conta ativa no Parserly."}
                </p>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="focus-ring inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-acid px-5 py-3 text-sm font-bold text-ink shadow-acid transition hover:-translate-y-0.5 hover:bg-mint disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-70"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                ) : (
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                )}
                {isSubmitting
                  ? "Enviando link..."
                  : isRegistrationFlow
                    ? "Enviar link de acesso"
                    : "Receber link de login"}
              </button>
            </form>

            {initialNotice ? (
              <div className="mt-5 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper">
                <div className="flex items-start gap-3">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
                  <p className="leading-6 text-paper/75">{initialNotice}</p>
                </div>
              </div>
            ) : null}

            {phase === "sent" ? (
              <div className="mt-5 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
                  <div>
                    <p className="font-semibold">Verifique o e-mail {sentTo}.</p>
                    <p className="mt-1 leading-6 text-paper/65">
                      {isRegistrationFlow
                        ? "O link chega em instantes, expira em 15 minutos e só pode ser usado uma vez."
                        : "Se houver uma conta ativa, o link de login chega em instantes e expira em 15 minutos."}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            {magicLink ? (
              <div className="mt-4 rounded-md border border-line/70 bg-night p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase text-paper/50">Link local</p>
                  <button
                    type="button"
                    onClick={handleCopyMagicLink}
                    className="focus-ring inline-flex min-h-9 items-center gap-2 rounded-md border border-line/70 bg-graphite px-3 py-2 text-xs font-semibold text-paper transition hover:border-acid/45 hover:bg-fog"
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
              >
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden="true" />
                <p>{error}</p>
              </div>
            ) : null}

            <div className="mt-6 flex items-start gap-3 border-t border-line/65 pt-5 text-sm text-paper/60">
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

    if (error.status === 404) {
      return "Este acesso é apenas para contas já cadastradas. Confira o e-mail e tente novamente.";
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
