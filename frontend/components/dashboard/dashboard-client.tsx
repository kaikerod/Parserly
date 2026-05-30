"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BookOpenText,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  FileSearch,
  History,
  Loader2,
  LogIn,
  LogOut,
  LockKeyhole,
  QrCode,
  RotateCw,
  ShieldCheck,
  Sparkles,
  UsersRound,
  UserPlus
} from "lucide-react";
import {
  ApiError,
  getAnalysisById,
  getAnalysisQuota,
  listAnalyses,
  submitResumeForAnalysis
} from "@/lib/api";
import { useAuthSession } from "@/hooks/use-auth-session";
import type { AnalysisHistoryItem, AnalysisResponse } from "@/types/analysis";
import { ALL_FEATURES_PERMISSION } from "@/types/auth";
import { AnalysisReport } from "./analysis-report";
import { Dropzone } from "./dropzone";
import { PaywallModal } from "./paywall-modal";

type SubmissionMode = "manual" | "after-payment";
type AnalysisRequestStep = "quota" | "analysis";

const HISTORY_DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "2-digit",
  hour: "2-digit",
  minute: "2-digit"
});
const HISTORY_PAGE_SIZE = 4;

const AUTHENTICATED_DASHBOARD_METRICS = [
  { label: "Quota grátis", value: "Incluída", detail: "até o limite inicial" },
  { label: "Arquivos", value: "PDF/DOCX", detail: "até 5 MB" },
  { label: "Após limite", value: "PIX", detail: "checkout no modal" }
];

const GUEST_DASHBOARD_METRICS = [
  { label: "Teste grátis", value: "Sem login", detail: "até o limite inicial" },
  { label: "Arquivos", value: "PDF/DOCX", detail: "até 5 MB" },
  { label: "Após limite", value: "Google", detail: "ou magic link" }
];

const AUTH_RESOLVING_DASHBOARD_METRICS = [
  { label: "Sessao", value: "Confirmando", detail: "validacao segura" },
  { label: "Arquivos", value: "PDF/DOCX", detail: "ate 5 MB" },
  { label: "Historico", value: "Aguarde", detail: "carregamento privado" }
];

const PAYMENT_REQUIRED_NOTICE =
  "Você atingiu o limite gratuito. Pague via PIX para liberar a próxima análise.";
const PAYMENT_NOT_CONFIRMED_NOTICE =
  "Pagamento não confirmado. O currículo ainda não foi enviado; pague via PIX para liberar a análise.";
const PAYMENT_EXPIRED_NOTICE =
  "O QR Code PIX expirou sem confirmação. Reabra o pagamento para gerar um novo QR Code.";
const QUOTA_CHECK_UNAVAILABLE_MESSAGE =
  "Não conseguimos verificar seus créditos agora. Tente novamente em instantes. Se você fechou o pagamento antes da confirmação, reabra o PIX e aguarde a confirmação.";
const ANALYSIS_LOADING_STEP_DELAY_MS = 1800;
const ANALYSIS_LOADING_STEPS = [
  "Analisando seu currículo",
  "Analisando sua experiência",
  "Extraindo suas habilidades",
  "Gerando recomendações"
] as const;

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

export function DashboardClient({
  isAuthenticated: initialIsAuthenticated,
  paymentRequired = false
}: DashboardClientProps) {
  const router = useRouter();
  const {
    isAuthenticated,
    isLoadingAuth,
    authError,
    accessLevel,
    permissions,
    refreshSession,
    logout: endSession
  } = useAuthSession(initialIsAuthenticated);
  const dashboardMetrics = isLoadingAuth
    ? AUTH_RESOLVING_DASHBOARD_METRICS
    : isAuthenticated
      ? AUTHENTICATED_DASHBOARD_METRICS
      : GUEST_DASHBOARD_METRICS;
  const historyRequestRef = useRef(0);
  const historyDetailAbortRef = useRef<AbortController | null>(null);
  const selectedHistoryIdRef = useRef<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeAnalysisLoadingStepIndex, setActiveAnalysisLoadingStepIndex] = useState(0);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isHistoryDetailLoading, setIsHistoryDetailLoading] = useState(false);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [submissionMode, setSubmissionMode] = useState<SubmissionMode>("manual");
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [hasPendingPixCharge, setHasPendingPixCharge] = useState(false);
  const [autoOpenedPayment, setAutoOpenedPayment] = useState(false);
  const [activeNavigationDetail, setActiveNavigationDetail] = useState(NAVIGATION_DETAILS[0]);
  const [error, setError] = useState<string | null>(null);
  const [paymentNotice, setPaymentNotice] = useState<string | null>(null);
  const ActiveNavigationIcon = activeNavigationDetail.icon;
  const paymentActionLabel = hasPendingPixCharge ? "Reabrir QR Code PIX" : "Abrir pagamento PIX";
  const activeAnalysisLoadingStep = ANALYSIS_LOADING_STEPS[activeAnalysisLoadingStepIndex];
  const hasFullFeatureAccess = permissions.includes(ALL_FEATURES_PERMISSION);

  useEffect(() => {
    const rotationInterval = window.setInterval(() => {
      setActiveNavigationDetail((currentItem) => {
        const currentIndex = NAVIGATION_DETAILS.findIndex((item) => item.label === currentItem.label);
        const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % NAVIGATION_DETAILS.length;
        return NAVIGATION_DETAILS[nextIndex];
      });
    }, 7000);

    return () => {
      window.clearInterval(rotationInterval);
    };
  }, []);

  useEffect(() => {
    selectedHistoryIdRef.current = selectedHistoryId;
  }, [selectedHistoryId]);

  useEffect(() => {
    if (!isSubmitting) {
      setActiveAnalysisLoadingStepIndex(0);
      return;
    }

    setActiveAnalysisLoadingStepIndex(0);
  }, [isSubmitting]);

  useEffect(() => {
    if (
      !isSubmitting ||
      activeAnalysisLoadingStepIndex >= ANALYSIS_LOADING_STEPS.length - 1
    ) {
      return;
    }

    const loadingStepTimer = window.setTimeout(() => {
      setActiveAnalysisLoadingStepIndex((currentIndex) =>
        Math.min(currentIndex + 1, ANALYSIS_LOADING_STEPS.length - 1)
      );
    }, ANALYSIS_LOADING_STEP_DELAY_MS);

    return () => {
      window.clearTimeout(loadingStepTimer);
    };
  }, [activeAnalysisLoadingStepIndex, isSubmitting]);

  const clearUserSpecificState = useCallback(() => {
    historyRequestRef.current += 1;
    historyDetailAbortRef.current?.abort();
    historyDetailAbortRef.current = null;
    const hadSelectedHistory = selectedHistoryIdRef.current !== null;
    selectedHistoryIdRef.current = null;

    if (hadSelectedHistory) {
      setAnalysis(null);
    }

    setAnalysisHistory([]);
    setHistoryTotal(0);
    setHistoryPage(0);
    setHistoryError(null);
    setSelectedHistoryId(null);
    setIsHistoryDetailLoading(false);
    setIsLoadingData(false);
  }, []);

  useEffect(() => {
    return () => {
      historyRequestRef.current += 1;
      historyDetailAbortRef.current?.abort();
    };
  }, []);

  const loadAnalysisHistory = useCallback(async (page: number, signal?: AbortSignal) => {
    if (!isAuthenticated || isLoadingAuth) {
      return;
    }

    const requestId = historyRequestRef.current + 1;
    historyRequestRef.current = requestId;
    setIsLoadingData(true);
    setHistoryError(null);

    try {
      const history = await listAnalyses(HISTORY_PAGE_SIZE, page * HISTORY_PAGE_SIZE, { signal });
      if (signal?.aborted || historyRequestRef.current !== requestId) {
        return;
      }

      setAnalysisHistory(history.items);
      setHistoryTotal(history.total);
    } catch (requestError) {
      if (isAbortError(requestError) || signal?.aborted || historyRequestRef.current !== requestId) {
        return;
      }

      if (requestError instanceof ApiError && requestError.status === 401) {
        clearUserSpecificState();
        await refreshSession();
        return;
      }

      setHistoryError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar o histórico."
      );
    } finally {
      if (!signal?.aborted && historyRequestRef.current === requestId) {
        setIsLoadingData(false);
      }
    }
  }, [clearUserSpecificState, isAuthenticated, isLoadingAuth, refreshSession]);

  useEffect(() => {
    if (isLoadingAuth || !isAuthenticated || !paymentRequired || autoOpenedPayment) {
      return;
    }

    setPaywallOpen(true);
    setError(null);
    setAutoOpenedPayment(true);
    window.history.replaceState(null, "", "/dashboard");
  }, [autoOpenedPayment, isAuthenticated, isLoadingAuth, paymentRequired]);

  useEffect(() => {
    if (isLoadingAuth) {
      return;
    }

    if (!isAuthenticated) {
      clearUserSpecificState();
      return;
    }

    const controller = new AbortController();
    void loadAnalysisHistory(historyPage, controller.signal);

    return () => {
      controller.abort();
      historyRequestRef.current += 1;
    };
  }, [clearUserSpecificState, historyPage, isAuthenticated, isLoadingAuth, loadAnalysisHistory]);

  const runAnalysis = useCallback(async (file: File, mode: SubmissionMode = "manual") => {
    setSelectedFile(file);
    setPendingFile(file);
    setError(null);
    setPaymentNotice(null);
    setSubmissionMode(mode);
    selectedHistoryIdRef.current = null;
    setSelectedHistoryId(null);
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
      selectedHistoryIdRef.current = result.id;
      setSelectedHistoryId(result.id);
      setPaywallOpen(false);
      setPendingFile(null);
      if (isAuthenticated) {
        if (historyPage === 0) {
          void loadAnalysisHistory(0);
        } else {
          setHistoryPage(0);
        }
      }
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
  }, [historyPage, isAuthenticated, loadAnalysisHistory, router]);

  const handleSelectHistoryItem = useCallback(async (item: AnalysisHistoryItem) => {
    if (!isAuthenticated || isLoadingAuth) {
      return;
    }

    historyDetailAbortRef.current?.abort();
    const controller = new AbortController();
    historyDetailAbortRef.current = controller;

    selectedHistoryIdRef.current = item.id;
    setSelectedHistoryId(item.id);
    setIsHistoryDetailLoading(true);
    setHistoryError(null);
    setError(null);
    setPaymentNotice(null);

    try {
      const savedAnalysis = await getAnalysisById(item.id, { signal: controller.signal });
      if (controller.signal.aborted || historyDetailAbortRef.current !== controller) {
        return;
      }

      setAnalysis(savedAnalysis);
      setSelectedFile(null);
      setPendingFile(null);
    } catch (requestError) {
      if (isAbortError(requestError) || historyDetailAbortRef.current !== controller) {
        return;
      }

      if (requestError instanceof ApiError && requestError.status === 401) {
        clearUserSpecificState();
        await refreshSession();
        return;
      }

      setHistoryError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível abrir a análise salva."
      );
    } finally {
      if (historyDetailAbortRef.current === controller) {
        historyDetailAbortRef.current = null;
        setIsHistoryDetailLoading(false);
      }
    }
  }, [clearUserSpecificState, isAuthenticated, isLoadingAuth, refreshSession]);

  const handleLogout = useCallback(async () => {
    clearUserSpecificState();

    try {
      await endSession();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }, [clearUserSpecificState, endSession, router]);

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
        <nav className="flex flex-wrap items-center justify-between gap-3 border-b border-line/55 pb-4 text-xs text-paper/60">
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

          <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:justify-end">
            <a
              href="/privacidade"
              className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 font-semibold text-paper/75 transition hover:border-acid/45 hover:bg-fog"
            >
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Privacidade
            </a>

            {isLoadingAuth ? (
              <button
                type="button"
                disabled
                className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-paper/60 disabled:cursor-wait disabled:opacity-80"
              >
                <Loader2 className="h-4 w-4 animate-spin text-acid" aria-hidden="true" />
                Confirmando sessao
              </button>
            ) : isAuthenticated ? (
              <>
                {hasFullFeatureAccess && accessLevel ? (
                  <span
                    className="hidden max-w-48 truncate rounded-md border border-acid/45 bg-acid/10 px-3 py-2 text-xs font-semibold text-acid sm:inline-flex"
                  >
                    {accessLevel}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={handleLogout}
                  className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-paper/75 transition hover:border-acid/45 hover:bg-fog disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Sair
                </button>
              </>
            ) : (
              <>
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
              </>
            )}
          </div>
        </nav>

        {authError ? (
          <div className="flex items-start justify-between gap-3 rounded-md border border-amber/35 bg-amber/10 px-4 py-3 text-sm text-paper">
            <div className="flex min-w-0 items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber" aria-hidden="true" />
              <p>{authError}</p>
            </div>
            <button
              type="button"
              onClick={() => void refreshSession()}
              className="focus-ring inline-flex min-h-9 shrink-0 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 text-xs font-semibold text-paper transition hover:border-acid/45 hover:bg-fog"
            >
              <RotateCw className="h-4 w-4" aria-hidden="true" />
              Tentar novamente
            </button>
          </div>
        ) : null}

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
          <div className="space-y-5">
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
              <AnalysisLoadingBanner
                activeStep={activeAnalysisLoadingStep}
                afterPayment={submissionMode === "after-payment"}
              />
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

            {analysis && selectedFile ? (
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

            {isLoadingAuth || isAuthenticated ? (
              <AnalysisHistoryPanel
                items={analysisHistory}
                total={historyTotal}
                currentPage={historyPage}
                pageSize={HISTORY_PAGE_SIZE}
                isAuthLoading={isLoadingAuth}
                isLoading={isLoadingData}
                isDetailLoading={isHistoryDetailLoading}
                selectedId={selectedHistoryId}
                error={historyError}
                onRefresh={() => void loadAnalysisHistory(historyPage)}
                onPageChange={setHistoryPage}
                onSelect={(item) => void handleSelectHistoryItem(item)}
              />
            ) : null}
          </div>

          <div
            className="min-w-0 rounded-md border border-line/75 bg-graphite/85 p-5 shadow-panel backdrop-blur"
            aria-busy={isSubmitting}
          >
            {isSubmitting ? (
              <AnalysisReportLoadingState
                activeStepIndex={activeAnalysisLoadingStepIndex}
                steps={ANALYSIS_LOADING_STEPS}
              />
            ) : analysis ? (
              <AnalysisReport analysis={analysis} />
            ) : (
              <EmptyReportState />
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

function AnalysisLoadingBanner({
  activeStep,
  afterPayment
}: {
  activeStep: string;
  afterPayment: boolean;
}) {
  return (
    <div
      className="mt-5 flex items-start gap-3 rounded-md border border-acid/25 bg-acid/10 px-4 py-3 text-sm text-paper"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-acid" aria-hidden="true" />
      <div className="min-w-0">
        {afterPayment ? (
          <p className="text-xs font-bold uppercase text-acid">Pagamento confirmado</p>
        ) : null}
        <p className="font-semibold">{activeStep}</p>
        {afterPayment ? (
          <p className="mt-1 text-xs leading-5 text-paper/60">Análise iniciada automaticamente.</p>
        ) : null}
      </div>
    </div>
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

interface AnalysisHistoryPanelProps {
  items: AnalysisHistoryItem[];
  total: number;
  currentPage: number;
  pageSize: number;
  isAuthLoading: boolean;
  isLoading: boolean;
  isDetailLoading: boolean;
  selectedId: string | null;
  error: string | null;
  onRefresh: () => void;
  onPageChange: (page: number) => void;
  onSelect: (item: AnalysisHistoryItem) => void;
}

function AnalysisHistoryPanel({
  items,
  total,
  currentPage,
  pageSize,
  isAuthLoading,
  isLoading,
  isDetailLoading,
  selectedId,
  error,
  onRefresh,
  onPageChange,
  onSelect
}: AnalysisHistoryPanelProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasMultiplePages = totalPages > 1;
  const canGoPrevious = currentPage > 0 && !isAuthLoading && !isLoading;
  const canGoNext = currentPage < totalPages - 1 && !isAuthLoading && !isLoading;
  const hasItems = items.length > 0;
  const startItem = hasItems ? currentPage * pageSize + 1 : 0;
  const endItem = hasItems ? currentPage * pageSize + items.length : 0;

  return (
    <section
      aria-labelledby="history-title"
      className="rounded-md border border-line/75 bg-graphite/90 p-5 shadow-panel backdrop-blur"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-copper">Histórico</p>
          <h2 id="history-title" className="mt-1 font-display text-2xl font-semibold">
            Análises salvas
          </h2>
          <p className="mt-1 text-xs text-paper/50">{total} registros encontrados</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {hasMultiplePages ? (
            <div className="hidden items-center rounded-md border border-line/70 bg-night/70 text-xs text-paper/55 sm:flex">
              <button
                type="button"
                onClick={() => onPageChange(currentPage - 1)}
                disabled={!canGoPrevious}
                className="focus-ring inline-flex h-10 items-center justify-center border-r border-line/70 px-3 transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Página anterior"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <span className="px-3">
                Página {currentPage + 1} de {totalPages}
              </span>
              <button
                type="button"
                onClick={() => onPageChange(currentPage + 1)}
                disabled={!canGoNext}
                className="focus-ring inline-flex h-10 items-center justify-center border-l border-line/70 px-3 transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Próxima página"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isAuthLoading || isLoading}
            className="focus-ring inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-line/70 bg-night text-paper/70 transition hover:border-acid/45 hover:bg-fog disabled:cursor-not-allowed disabled:opacity-60"
            aria-label="Atualizar histórico"
          >
            {isAuthLoading || isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <RotateCw className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 flex items-start gap-3 rounded-md border border-coral/35 bg-coral/10 px-3 py-3 text-sm text-paper">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-coral" aria-hidden="true" />
          <p>{error}</p>
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {isAuthLoading ? (
          <div className="flex items-center gap-3 rounded-md border border-line/70 bg-night/70 px-3 py-4 text-sm text-paper/60">
            <Loader2 className="h-4 w-4 animate-spin text-acid" aria-hidden="true" />
            Confirmando sessao antes de carregar o historico...
          </div>
        ) : null}

        {!isAuthLoading && isLoading && items.length === 0 ? (
          <div className="flex items-center gap-3 rounded-md border border-line/70 bg-night/70 px-3 py-4 text-sm text-paper/60">
            <Loader2 className="h-4 w-4 animate-spin text-acid" aria-hidden="true" />
            Carregando histórico...
          </div>
        ) : null}

        {!isAuthLoading && !isLoading && items.length === 0 ? (
          <div className="rounded-md border border-dashed border-line/70 bg-night/50 px-4 py-5 text-sm text-paper/60">
            <History className="mb-3 h-5 w-5 text-paper/35" aria-hidden="true" />
            Nenhuma análise salva ainda.
          </div>
        ) : null}

        {!isAuthLoading && items.map((item) => {
          const isSelected = selectedId === item.id;
          const isOpening = isSelected && isDetailLoading;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item)}
              className={[
                "focus-ring grid min-h-20 w-full grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border px-3 py-3 text-left transition",
                isSelected
                  ? "border-acid/50 bg-acid/10"
                  : "border-line/70 bg-night/65 hover:border-acid/35 hover:bg-fog"
              ].join(" ")}
              aria-pressed={isSelected}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-paper">
                  {item.filename}
                </span>
                <span className="mt-2 flex items-center gap-1.5 text-xs text-paper/50">
                  <CalendarClock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {formatAnalysisDate(item.created_at)}
                </span>
              </span>
              <span className="rounded-md border border-line/70 bg-graphite px-2.5 py-1 text-sm font-bold text-acid">
                {item.score}
              </span>
              {isOpening ? (
                <Loader2 className="h-4 w-4 animate-spin text-acid" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-4 w-4 text-paper/35" aria-hidden="true" />
              )}
            </button>
          );
        })}
      </div>

      {hasMultiplePages ? (
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-line/60 pt-4 text-xs text-paper/55">
          <p>
            Mostrando {startItem}-{endItem} de {total}
          </p>
          <div className="flex items-center gap-2 sm:hidden">
            <button
              type="button"
              onClick={() => onPageChange(currentPage - 1)}
              disabled={!canGoPrevious}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-line/70 bg-night px-3 font-semibold text-paper/75 transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Página anterior"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Anterior
            </button>
            <button
              type="button"
              onClick={() => onPageChange(currentPage + 1)}
              disabled={!canGoNext}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-line/70 bg-night px-3 font-semibold text-paper/75 transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Próxima página"
            >
              Próxima
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function AnalysisReportLoadingState({
  activeStepIndex,
  steps
}: {
  activeStepIndex: number;
  steps: readonly string[];
}) {
  const activeStep = steps[activeStepIndex];

  return (
    <section
      className="panel-grid flex min-h-[34rem] flex-col justify-center rounded-md border border-acid/30 bg-night/55 px-5 py-8"
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-md bg-acid text-ink shadow-acid">
        <Loader2 className="h-7 w-7 animate-spin" aria-hidden="true" />
      </div>

      <div className="mx-auto mt-5 max-w-xl text-center">
        <p className="text-xs font-bold uppercase text-copper">Análise em andamento</p>
        <h2 className="mt-2 font-display text-3xl font-semibold text-paper">{activeStep}</h2>
        <p className="mt-3 text-sm leading-6 text-paper/62">
          Estamos preparando a leitura ATS e as recomendações para o arquivo enviado.
        </p>
      </div>

      <ol className="mx-auto mt-8 grid w-full max-w-2xl gap-3">
        {steps.map((step, index) => {
          const isActive = index === activeStepIndex;
          const isComplete = index < activeStepIndex;

          return (
            <li
              key={step}
              className={[
                "flex min-h-14 items-center gap-3 rounded-md border px-4 py-3 text-left transition",
                isActive
                  ? "border-acid/45 bg-acid/10 text-paper shadow-acid"
                  : isComplete
                    ? "border-teal/35 bg-teal/10 text-paper/80"
                    : "border-line/70 bg-graphite/80 text-paper/48"
              ].join(" ")}
              aria-current={isActive ? "step" : undefined}
            >
              <span
                className={[
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs font-bold",
                  isActive
                    ? "border-acid bg-acid text-ink"
                    : isComplete
                      ? "border-teal bg-teal text-ink"
                      : "border-line/80 bg-night text-paper/45"
                ].join(" ")}
              >
                {isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : isComplete ? (
                  <span aria-hidden="true">✓</span>
                ) : (
                  index + 1
                )}
              </span>
              <span className="min-w-0 text-sm font-semibold">{step}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function EmptyReportState() {
  return (
    <section className="panel-grid flex min-h-[34rem] flex-col items-center justify-center rounded-md border border-dashed border-line/75 bg-night/50 px-6 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-md bg-violet text-paper shadow-tool">
        <FileSearch className="h-7 w-7" aria-hidden="true" />
      </div>
      <h2 className="mt-5 font-display text-3xl font-semibold text-paper">
        Seu relatório aparecerá aqui
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

function formatAnalysisDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Data indisponível";
  }

  return HISTORY_DATE_FORMATTER.format(date);
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

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

