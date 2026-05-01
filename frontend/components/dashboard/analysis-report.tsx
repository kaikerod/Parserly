"use client";

import {
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  CheckCircle2,
  CircleDot,
  Target
} from "lucide-react";
import type {
  AnalysisResponse,
  CategoryKey,
  RecommendationPriority
} from "@/types/analysis";

const CATEGORY_ORDER: CategoryKey[] = [
  "keywords",
  "formatting",
  "structure",
  "contact_info",
  "quantifiable_achievements"
];

const CATEGORY_LABELS: Record<CategoryKey, string> = {
  keywords: "Palavras-chave",
  formatting: "Formatação ATS",
  structure: "Estrutura",
  contact_info: "Contato",
  quantifiable_achievements: "Resultados"
};

const PRIORITY_META: Record<
  RecommendationPriority,
  { label: string; className: string; icon: typeof AlertTriangle }
> = {
  high: {
    label: "Alta",
    className: "border-coral/40 bg-coral/15 text-coral",
    icon: AlertTriangle
  },
  medium: {
    label: "Média",
    className: "border-copper/40 bg-copper/15 text-copper",
    icon: CircleDot
  },
  low: {
    label: "Baixa",
    className: "border-acid/35 bg-acid/10 text-acid",
    icon: CheckCircle2
  }
};

const PRIORITY_RANK: Record<RecommendationPriority, number> = {
  high: 0,
  medium: 1,
  low: 2
};

interface AnalysisReportProps {
  analysis: AnalysisResponse;
}

export function AnalysisReport({ analysis }: AnalysisReportProps) {
  const report = analysis.report_json;
  const recommendations = [...report.recommendations].sort(
    (left, right) => PRIORITY_RANK[left.priority] - PRIORITY_RANK[right.priority]
  );
  const score = Math.max(0, Math.min(100, analysis.score));

  return (
    <section aria-labelledby="analysis-report-title" className="space-y-6 text-paper">
      <div className="flex flex-col gap-4 border-b border-line/70 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-acid">Relatório ATS</p>
          <h2
            id="analysis-report-title"
            className="mt-2 break-words font-display text-3xl font-semibold"
          >
            {analysis.filename}
          </h2>
          <p className="mt-2 text-sm text-paper/60">
            {report.detected_role
              ? `Cargo detectado: ${report.detected_role}`
              : "Cargo não identificado no currículo."}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-line/70 bg-night px-4 py-2 text-sm text-paper/70 shadow-tool">
          <BadgeCheck className="h-4 w-4 text-acid" aria-hidden="true" />
          <span>{analysis.analyses_used} análises usadas</span>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[18rem_1fr]">
        <div className="rounded-md border border-line/70 bg-night p-6 text-paper shadow-tool">
          <div
            className="mx-auto flex h-44 w-44 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(#45ff73 ${score * 3.6}deg, rgba(244,241,234,0.14) 0deg)`
            }}
            aria-label={`Nota geral ${score} de 100`}
          >
            <div className="flex h-32 w-32 flex-col items-center justify-center rounded-full border border-line bg-graphite">
              <span className="font-display text-5xl font-semibold leading-none text-paper">
                {score}
              </span>
              <span className="mt-1 text-xs uppercase text-paper/50">de 100</span>
            </div>
          </div>
          <div className="mt-6 space-y-2 text-center">
            <p className="text-sm font-semibold uppercase text-acid">Nota geral</p>
            <p className="text-sm leading-6 text-paper/60">
              Combina aderência a palavras-chave, legibilidade do parser e clareza da estrutura.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {CATEGORY_ORDER.map((categoryKey) => {
            const category = report.categories[categoryKey];

            return (
              <article
                key={categoryKey}
                className="rounded-md border border-line/70 bg-night/70 p-4 shadow-tool"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-paper">
                      {CATEGORY_LABELS[categoryKey]}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-paper/60">{category.feedback}</p>
                  </div>
                  <span className="rounded-md border border-line/70 bg-graphite px-2.5 py-1 text-sm font-bold text-acid">
                    {category.score}
                  </span>
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-line/65">
                  <div
                    className="h-full rounded-full bg-acid"
                    style={{ width: `${Math.max(0, Math.min(100, category.score))}%` }}
                  />
                </div>
              </article>
            );
          })}
        </div>
      </div>

      <section aria-labelledby="recommendations-title" className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-copper">Próximas ações</p>
            <h3 id="recommendations-title" className="mt-1 font-display text-2xl font-semibold">
              Recomendações priorizadas
            </h3>
          </div>
          <Target className="h-7 w-7 text-violet" aria-hidden="true" />
        </div>

        <div className="space-y-3">
          {recommendations.map((recommendation, index) => {
            const meta = PRIORITY_META[recommendation.priority];
            const PriorityIcon = meta.icon;

            return (
              <article
                key={`${recommendation.priority}-${recommendation.action}-${index}`}
                className="grid gap-4 rounded-md border border-line/70 bg-night/70 p-4 shadow-tool md:grid-cols-[9rem_1fr]"
              >
                <div>
                  <span
                    className={[
                      "inline-flex min-w-24 items-center gap-2 rounded-md border px-3 py-1 text-xs font-bold uppercase",
                      meta.className
                    ].join(" ")}
                  >
                    <PriorityIcon className="h-3.5 w-3.5" aria-hidden="true" />
                    {meta.label}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold leading-6 text-paper">
                    {recommendation.action}
                  </p>
                  <p className="mt-2 flex gap-2 text-sm leading-6 text-paper/60">
                    <BarChart3 className="mt-0.5 h-4 w-4 shrink-0 text-teal" aria-hidden="true" />
                    <span>{recommendation.expected_impact}</span>
                  </p>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </section>
  );
}
