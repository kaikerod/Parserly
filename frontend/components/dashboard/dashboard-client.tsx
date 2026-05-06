"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BookOpenText,
  CreditCard,
  FileSearch,
  Loader2,
  LogIn,
  LogOut,
  LockKeyhole,
  QrCode,
  RotateCw,
  Sparkles,
  UsersRound,
  UserPlus
} from "lucide-react";
import { ApiError, getAnalysisQuota, logout, submitResumeForAnalysis } from "@/lib/api";
import type { AnalysisResponse } from "@/types/analysis";
import { AnalysisReport } from "./analysis-report";
import { Dropzone } from "./dropzone";
import { PaywallModal } from "./paywall-modal";

type SubmissionMode = "manual" | "after-payment";
type AnalysisRequestStep = "quota" | "analysis";

const AUTHENTICATED_DASHBOARD_METRICS = [
  { label: "Quota grátis", value: "3", detail: "análises por conta" },
  { label: "Arquivos", value: "PDF/DOCX", detail: "até 5 MB" },
  { label: "Após limite", value: "PIX", detail: "checkout no modal" }
];

const GUEST_DASHBOARD_METRICS = [
  { label: "Sem cadastro", value: "3", detail: "análises grátis" },
  { label: "Arquivos", value: "PDF/DOCX", detail: "até 5 MB" },
  { label: "Após limite", value: "Cadastro", detail: "magic link por e-mail" }
];

const PAYMENT_REQUIRED_NOTICE =
  "Você atingiu o limite gratuito. Pague via PIX para liberar a próxima análise.";
const PAYMENT_NOT_CONFIRMED_NOTICE =
  "Pagamento não confirmado. O currículo ainda não foi enviado; pague via PIX para liberar a análise.";
const PAYMENT_EXPIRED_NOTICE =
  "O QR Code PIX expirou sem confirmação. Reabra o pagamento para gerar um novo QR Code.";
const QUOTA_CHECK_UNAVAILABLE_MESSAGE =
  "Não conseguimos verificar seus créditos agora. Tente novamente em instantes. Se você fechou o pagamento antes da confirmação, reabra o PIX e aguarde a confirmação.";

const NAVIGATION_DETAILS = [
  {
    label: "Produto",
    title: "Análise ATS com diagnóstico acionável",
    description:
      "Envie um currículo em PDF ou DOCX para receber score, leitura por categoria e recomendações priorizadas antes da candidatura.",
    icon: Sparkles
  },
  {
    label: "Guias",
    title: "Boas práticas para passar por filtros ATS",
    description:
      "Consulte orientações sobre palavras-chave, estrutura de seções, formatação compatível e ajustes que melhoram a leitura automática.",
    icon: BookOpenText
  },
  {
    label: "Pagamento",
    title: "Análises extras com checkout via PIX",
    description:
      "Use as análises gratuitas e, ao atingir o limite, libere novas avaliações pelo fluxo de pagamento seguro integrado ao Mercado Pago.",
    icon: CreditCard
  },
  {
    label: "Equipe",
    title: "Produto guiado por carreira, dados e engenharia",
    description:
      "O Parserly combina critérios técnicos de parsing, experiência de candidatura e IA para transformar currículos em planos claros de melhoria.",
    icon: UsersRound
  }
];

interface DashboardClientProps {
  isAuthenticated: boolean;
  paymentRequired?: boolean;
}

export function DashboardClient({ isAuthenticated, paymentRequired = false }: DashboardClientProps) {
  const router = useRouter();
  const dashboardMetrics = isAuthenticated
    ? AUTHENTICATED_DASHBOARD_METRICS
    : GUEST_DASHBOARD_METRICS;
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [submissionMode, setSubmissionMode] = useState<SubmissionMode>("manual");
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [hasPendingPixCharge, setHasPendingPixCharge] = useState(false);
  const [autoOpenedPayment, setAutoOpenedPayment] = useState(false);
  const [activeNavigationDetail, setActiveNavigationDetail] = useState(NAVIGATION_DETAILS[0]);
  const [error, setError] = useState<string | null>(null);
  const [paymentNotice, setPaymentNotice] = useState<string | null>(null);
  const ActiveNavigationIcon = activeNavigationDetail.icon;
  const paymentActionLabel = hasPendingPixCharge ? "Reabrir QR Code PIX" : "Abrir pagamento PIX";

  useEffect(() => {
    if (!isAuthenticated || !paymentRequired || autoOpenedPayment) {
      return;
    }

    setPaywallOpen(true);
    setError(null);
    setAutoOpenedPayment(true);
    window.history.replaceState(null, "", "/dashboard");
  }, [autoOpenedPayment, isAuthenticated, paymentRequired]);

  const runAnalysis = useCallback(async (file: File, mode: SubmissionMode = "manual") => {
    setSelectedFile(file);
    setPendingFile(file);
    setError(null);
    setPaymentNotice(null);
    setSubmissionMode(mode);
    setIsSubmitting(true);

    let requestStep: AnalysisRequestStep = "quota";

    try {
      const quota = await getAnalysisQuota();
      if (quota.registration_required) {
        router.replace("/login?reason=free-limit");
        return;
      }

      if (quota.payment_required) {
        setPaymentNotice(quota.message ?? PAYMENT_REQUIRED_NOTICE);
        setPaywallOpen(true);
        return;
      }

      requestStep = "analysis";
      const result = await submitResumeForAnalysis(file);
      setAnalysis(result);
      setPaywallOpen(false);
      setPendingFile(null);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 402) {
        setPaymentNotice(requestError.message || PAYMENT_REQUIRED_NOTICE);
        setPaywallOpen(true);
        return;
      }

      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace(
          isRegistrationRequiredError(requestError) ? "/login?reason=free-limit" : "/login"
        );
        return;
      }

      setError(resolveAnalysisError(requestError, requestStep));
    } finally {
      setIsSubmitting(false);
    }
  }, [router]);

  const handleLogout = useCallback(async () => {
    setIsLoggingOut(true);

    try {
      await logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }, [router]);

  const handlePaymentConfirmed = useCallback(() => {
    setPaywallOpen(false);
    setHasPendingPixCharge(false);
    setError(null);

    if (pendingFile) {
      void runAnalysis(pendingFile, "after-payment");
      return;
    }

    setPaymentNotice("Pagamento confirmado. Você tem 10 análises liberadas.");
  }, [pendingFile, runAnalysis]);

  const handlePaywallClosed = useCallback(() => {
    setPaywallOpen(false);
    setPaymentNotice(pendingFile ? PAYMENT_NOT_CONFIRMED_NOTICE : PAYMENT_REQUIRED_NOTICE);
  }, [pendingFile]);

  const handleOpenPayment = useCallback(() => {
    setError(null);
    setPaywallOpen(true);
  }, []);

  const handlePixChargeCreated = useCallback(() => {
    setHasPendingPixCharge(true);
    setPaymentNotice(null);
  }, []);

  const handlePixChargeExpired = useCallback(() => {
    setHasPendingPixCharge(false);
    setPaymentNotice(PAYMENT_EXPIRED_NOTICE);
  }, []);

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-5 text-paper sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-[linear-gradient(115deg,rgba(109,93,252,0.22),transparent_42%),linear-gradient(250deg,rgba(69,255,115,0.12),transparent_36%)]" />

      <div className="mx-auto flex max-w-7xl flex-col gap-7">
        <nav className="flex items-center justify-between border-b border-line/55 pb-4 text-xs text-paper/60">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-violet text-paper shadow-glow">
              <FileSearch className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="flex min-w-0 items-center gap-3">
              <span className="font-display text-base font-semibold text-paper">Parserly</span>
              <span className="hidden text-paper/30 sm:inline">/</span>
              <span className="hidden truncate sm:inline">Análise ATS para currículos</span>
            </div>
          </div>

          <div className="hidden items-center gap-2 md:flex" aria-label="Navegação principal">
            {NAVIGATION_DETAILS.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => setActiveNavigationDetail(item)}
                className={`focus-ring rounded-md px-3 py-2 text-xs font-semibold transition ${
                  activeNavigationDetail.label === item.label
                    ? "bg-paper text-ink"
                    : "text-paper/60 hover:bg-fog hover:text-paper"
                }`}
                aria-pressed={activeNavigationDetail.label === item.label}
              >
                {item.label}
              </button>
            ))}
          </div>

          {isAuthenticated ? (
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-paper/75 transition hover:border-acid/45 hover:bg-fog disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoggingOut ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <LogOut className="h-4 w-4" aria-hidden="true" />
              )}
              Sair
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <a
                href="/login"
                className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-paper/75 transition hover:border-acid/45 hover:bg-fog"
              >
                <LogIn className="h-4 w-4" aria-hidden="true" />
                Entrar
              </a>
              <a
                href="/login?intent=registration"
                className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-paper/75 transition hover:border-acid/45 hover:bg-fog"
              >
                <UserPlus className="h-4 w-4" aria-hidden="true" />
                Cadastrar
              </a>
            </div>
          )}
        </nav>

        <section
          aria-live="polite"
          className="hidden items-start gap-4 rounded-md border border-line/70 bg-graphite/80 p-4 shadow-tool backdrop-blur md:flex"
        >
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-night text-acid">
            <ActiveNavigationIcon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-copper">{activeNavigationDetail.label}</p>
            <h2 className="mt-1 font-display text-xl font-semibold text-paper">
              {activeNavigationDetail.title}
            </h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-paper/62">
              {activeNavigationDetail.description}
            </p>
          </div>
        </section>

        <header className="grid gap-6 border-b border-line/55 pb-7 lg:grid-cols-[1fr_32rem] lg:items-end">
          <div>
            <div className="inline-flex items-center gap-2 rounded-md border border-line/70 bg-graphite/80 px-3 py-1.5 text-xs font-bold uppercase text-paper/70 shadow-tool backdrop-blur">
              <FileSearch className="h-4 w-4 text-acid" aria-hidden="true" />
              ATS Resume Analyzer
            </div>
            <h1 className="mt-5 max-w-3xl font-display text-5xl font-semibold leading-none text-paper md:text-6xl">
              Seu currículo.
              <br />
              Claramente <span className="accent-text">estruturado.</span>
            </h1>
            <div className="mt-5 max-w-2xl text-sm leading-6 text-paper/65">
              <p>
                Envie um PDF ou DOCX, receba a nota ATS e veja as correções que mais impactam sua
                próxima candidatura.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {dashboardMetrics.map((metric) => (
              <div
                key={metric.label}
                className="rounded-md border border-line/70 bg-graphite/80 p-4 shadow-tool backdrop-blur"
              >
                <p className="text-xs font-semibold uppercase text-paper/45">{metric.label}</p>
                <p className="mt-2 font-display text-2xl font-semibold text-copper">
                  {metric.value}
                </p>
                <p className="mt-1 text-xs text-paper/55">{metric.detail}</p>
              </div>
            ))}
          </div>
        </header>

        <div className="grid gap-5 lg:grid-cols-[25rem_1fr]">
          <section
            id="upload-panel"
            aria-labelledby="upload-title"
            className="rounded-md border border-line/75 bg-graphite/90 p-5 shadow-panel backdrop-blur"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase text-acid">Upload</p>
                <h2 id="upload-title" className="mt-1 font-display text-2xl font-semibold">
                  Novo currículo
                </h2>
              </div>
              <LockKeyhole className="h-6 w-6 text-paper/30" aria-hidden="true" />
            </div>

            <Dropzone
              disabled={isSubmitting}
              selectedFile={selectedFile}
              onFileAccepted={(file) => void runAnalysis(file)}
            />

            {isSubmitting ? (
              <div className="mt-5 flex items-center gap-3 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper">
                <Loader2 className="h-5 w-5 animate-spin text-acid" aria-hidden="true" />
                {submissionMode === "after-payment"
                  ? "Pagamento confirmado. Análise iniciada automaticamente."
                  : "Enviando e analisando o currículo..."}
              </div>
            ) : null}

            {error ? (
              <div className="mt-5 flex items-start gap-3 rounded-md border border-coral/35 bg-coral/10 px-4 py-3 text-sm text-paper">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden="true" />
                <div className="min-w-0">
                  <p>{error}</p>
                  {hasPendingPixCharge ? (
                    <PaymentActionButton label="Reabrir QR Code PIX" onClick={handleOpenPayment} />
                  ) : null}
                </div>
              </div>
            ) : null}

            {paymentNotice ? (
              <div className="mt-5 flex items-start gap-3 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper">
                <CreditCard className="mt-0.5 h-5 w-5 shrink-0 text-acid" aria-hidden="true" />
                <div className="min-w-0">
                  <p>{paymentNotice}</p>
                  {isAuthenticated ? (
                    <PaymentActionButton label={paymentActionLabel} onClick={handleOpenPayment} />
                  ) : null}
                </div>
              </div>
            ) : null}

            {analysis ? (
              <button
                type="button"
                onClick={() => {
                  if (selectedFile) {
                    void runAnalysis(selectedFile);
                  }
                }}
                disabled={isSubmitting || !selectedFile}
                className="focus-ring mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-line/80 bg-night px-4 py-2 text-sm font-semibold text-paper transition hover:border-acid/45 hover:bg-fog disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RotateCw className="h-4 w-4" aria-hidden="true" />
                Reanalisar arquivo selecionado
              </button>
            ) : null}
          </section>

          <div className="min-w-0 rounded-md border border-line/75 bg-graphite/85 p-5 shadow-panel backdrop-blur">
            {analysis ? (
              <AnalysisReport analysis={analysis} />
            ) : (
              <EmptyReportState isSubmitting={isSubmitting} />
            )}
          </div>
        </div>
      </div>

      <PaywallModal
        open={paywallOpen}
        fileName={pendingFile?.name}
        onClose={handlePaywallClosed}
        onChargeCreated={handlePixChargeCreated}
        onChargeExpired={handlePixChargeExpired}
        onPaymentConfirmed={handlePaymentConfirmed}
      />
    </main>
  );
}

function PaymentActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="focus-ring mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-xs font-semibold text-paper transition hover:border-acid/45 hover:bg-fog"
    >
      <QrCode className="h-4 w-4 text-acid" aria-hidden="true" />
      {label}
    </button>
  );
}

function EmptyReportState({ isSubmitting }: { isSubmitting: boolean }) {
  return (
    <section className="panel-grid flex min-h-[34rem] flex-col items-center justify-center rounded-md border border-dashed border-line/75 bg-night/50 px-6 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-md bg-violet text-paper shadow-tool">
        {isSubmitting ? (
          <Loader2 className="h-7 w-7 animate-spin" aria-hidden="true" />
        ) : (
          <FileSearch className="h-7 w-7" aria-hidden="true" />
        )}
      </div>
      <h2 className="mt-5 font-display text-3xl font-semibold text-paper">
        {isSubmitting ? "Preparando relatório" : "Seu relatório aparecerá aqui"}
      </h2>
      <p className="mt-3 max-w-lg text-sm leading-6 text-paper/60">
        Quando a análise retornar, a nota, os diagnósticos por categoria e as recomendações
        priorizadas serão renderizados neste espaço.
      </p>

      <div className="mt-8 grid w-full max-w-2xl gap-3 text-left sm:grid-cols-3">
        <div className="rounded-md border border-line/70 bg-graphite/85 p-4">
          <p className="text-xs font-semibold uppercase text-paper/45">Score ATS</p>
          <p className="mt-3 font-display text-4xl font-semibold text-acid">82</p>
          <div className="mt-3 h-2 rounded-full bg-line/70">
            <div className="h-full w-4/5 rounded-full bg-acid" />
          </div>
        </div>
        <div className="rounded-md border border-line/70 bg-graphite/85 p-4">
          <p className="text-xs font-semibold uppercase text-paper/45">Estrutura</p>
          <div className="mt-4 space-y-2">
            <div className="h-2 w-11/12 rounded-full bg-violet" />
            <div className="h-2 w-8/12 rounded-full bg-paper/20" />
            <div className="h-2 w-10/12 rounded-full bg-paper/20" />
          </div>
        </div>
        <div className="rounded-md border border-line/70 bg-graphite/85 p-4">
          <p className="text-xs font-semibold uppercase text-paper/45">Prioridade</p>
          <p className="mt-3 font-display text-3xl font-semibold text-copper">Alta</p>
          <p className="mt-2 text-xs text-paper/55">palavras-chave</p>
        </div>
      </div>
    </section>
  );
}

function isRegistrationRequiredError(error: ApiError) {
  if (!isRecord(error.detail)) {
    return false;
  }

  const detail = error.detail.detail;
  return isRecord(detail) && detail.error === "registration_required";
}

function resolveAnalysisError(error: unknown, requestStep: AnalysisRequestStep) {
  if (requestStep === "quota" && error instanceof ApiError && error.status >= 500) {
    return QUOTA_CHECK_UNAVAILABLE_MESSAGE;
  }

  return error instanceof Error ? error.message : "Não foi possível concluir a análise.";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
