"use client";

import { useCallback, useState } from "react";
import { AlertCircle, FileSearch, Loader2, LockKeyhole, RotateCw } from "lucide-react";
import { ApiError, submitResumeForAnalysis } from "@/lib/api";
import type { AnalysisResponse } from "@/types/analysis";
import { AnalysisReport } from "./analysis-report";
import { Dropzone } from "./dropzone";
import { PaywallModal } from "./paywall-modal";

type SubmissionMode = "manual" | "after-payment";

export function DashboardClient() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionMode, setSubmissionMode] = useState<SubmissionMode>("manual");
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = useCallback(async (file: File, mode: SubmissionMode = "manual") => {
    setSelectedFile(file);
    setPendingFile(file);
    setError(null);
    setSubmissionMode(mode);
    setIsSubmitting(true);

    try {
      const result = await submitResumeForAnalysis(file);
      setAnalysis(result);
      setPaywallOpen(false);
      setPendingFile(null);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 402) {
        setPaywallOpen(true);
        return;
      }

      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível concluir a análise."
      );
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handlePaymentConfirmed = useCallback(() => {
    setPaywallOpen(false);

    if (pendingFile) {
      void runAnalysis(pendingFile, "after-payment");
    }
  }, [pendingFile, runAnalysis]);

  return (
    <main className="min-h-screen px-4 py-6 text-ink sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <header className="flex flex-col gap-5 border-b border-graphite/15 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-graphite/15 bg-white px-3 py-1 text-xs font-bold uppercase text-graphite/70 shadow-tool">
              <FileSearch className="h-4 w-4 text-teal" aria-hidden="true" />
              ATS Resume Analyzer
            </div>
            <h1 className="mt-4 max-w-3xl font-display text-4xl font-semibold leading-tight text-ink md:text-5xl">
              Dashboard de análise de currículo
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-graphite/75">
              Envie um PDF ou DOCX, receba a nota ATS e veja as correções que mais impactam sua
              próxima candidatura.
            </p>
          </div>

          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:w-[26rem]">
            <div className="rounded-md border border-graphite/15 bg-white px-4 py-3 shadow-tool">
              <p className="text-xs font-semibold uppercase text-graphite/55">Quota grátis</p>
              <p className="mt-1 font-semibold">3 análises por usuário</p>
            </div>
            <div className="rounded-md border border-graphite/15 bg-white px-4 py-3 shadow-tool">
              <p className="text-xs font-semibold uppercase text-graphite/55">Após o limite</p>
              <p className="mt-1 font-semibold">PIX avulso no modal</p>
            </div>
          </div>
        </header>

        <div className="grid gap-8 lg:grid-cols-[25rem_1fr]">
          <section
            aria-labelledby="upload-title"
            className="rounded-md border border-graphite/15 bg-paper/90 p-5 shadow-paper"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase text-teal">Upload</p>
                <h2 id="upload-title" className="mt-1 font-display text-2xl font-semibold">
                  Novo currículo
                </h2>
              </div>
              <LockKeyhole className="h-6 w-6 text-graphite/45" aria-hidden="true" />
            </div>

            <Dropzone
              disabled={isSubmitting}
              selectedFile={selectedFile}
              onFileAccepted={(file) => void runAnalysis(file)}
            />

            {isSubmitting ? (
              <div className="mt-5 flex items-center gap-3 rounded-md border border-teal/25 bg-teal/10 px-4 py-3 text-sm text-ink">
                <Loader2 className="h-5 w-5 animate-spin text-teal" aria-hidden="true" />
                {submissionMode === "after-payment"
                  ? "Pagamento confirmado. Análise iniciada automaticamente."
                  : "Enviando e analisando o currículo..."}
              </div>
            ) : null}

            {error ? (
              <div className="mt-5 flex items-start gap-3 rounded-md border border-coral/30 bg-coral/10 px-4 py-3 text-sm text-ink">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden="true" />
                <p>{error}</p>
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
                className="focus-ring mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-graphite/15 bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RotateCw className="h-4 w-4" aria-hidden="true" />
                Reanalisar arquivo selecionado
              </button>
            ) : null}
          </section>

          <div className="min-w-0 rounded-md border border-graphite/15 bg-paper/90 p-5 shadow-paper">
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
        onClose={() => setPaywallOpen(false)}
        onPaymentConfirmed={handlePaymentConfirmed}
      />
    </main>
  );
}

function EmptyReportState({ isSubmitting }: { isSubmitting: boolean }) {
  return (
    <section className="flex min-h-[34rem] flex-col items-center justify-center rounded-md border border-dashed border-graphite/20 bg-white/60 px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-md bg-ink text-paper shadow-tool">
        {isSubmitting ? (
          <Loader2 className="h-7 w-7 animate-spin" aria-hidden="true" />
        ) : (
          <FileSearch className="h-7 w-7" aria-hidden="true" />
        )}
      </div>
      <h2 className="mt-5 font-display text-2xl font-semibold text-ink">
        {isSubmitting ? "Preparando relatório" : "Seu relatório aparecerá aqui"}
      </h2>
      <p className="mt-3 max-w-lg text-sm leading-6 text-graphite/70">
        A página permanece no dashboard: quando a análise retorna, a nota, os diagnósticos por
        categoria e as recomendações priorizadas são renderizados neste espaço.
      </p>
    </section>
  );
}
