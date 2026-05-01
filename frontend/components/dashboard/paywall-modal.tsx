"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  CreditCard,
  Loader2,
  QrCode,
  RefreshCcw,
  ShieldCheck,
  X
} from "lucide-react";
import { apiPath, createPixCharge } from "@/lib/api";
import type { CreateChargeResponse, PaymentStreamEvent } from "@/types/payment";

type PaywallPhase = "idle" | "creating" | "waiting" | "confirmed" | "expired" | "error";

interface PaywallModalProps {
  open: boolean;
  fileName?: string;
  onClose: () => void;
  onPaymentConfirmed: () => void;
}

export function PaywallModal({
  open,
  fileName,
  onClose,
  onPaymentConfirmed
}: PaywallModalProps) {
  const [phase, setPhase] = useState<PaywallPhase>("idle");
  const [charge, setCharge] = useState<CreateChargeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [qrCodeSrc, setQrCodeSrc] = useState<string | null>(null);
  const confirmedRef = useRef(false);

  const amount = charge ? formatCurrency(charge.amount_cents) : "R$ 9,90";

  useEffect(() => {
    if (!open) {
      setPhase("idle");
      setCharge(null);
      setError(null);
      setCopyState("idle");
      setRemainingSeconds(0);
      setQrCodeSrc(null);
      confirmedRef.current = false;
    }
  }, [open]);

  useEffect(() => {
    let cancelled = false;

    async function resolveQrCode() {
      setQrCodeSrc(null);

      if (!charge) {
        return;
      }

      const providedQrCode = normalizeQrCodeSource(charge.pix_qr_code);
      if (providedQrCode) {
        setQrCodeSrc(providedQrCode);
        return;
      }

      try {
        const QRCode = await import("qrcode");
        const generatedQrCode = await QRCode.toDataURL(charge.pix_copy_paste, {
          width: 512,
          margin: 1,
          errorCorrectionLevel: "M",
          color: {
            dark: "#191916",
            light: "#ffffff"
          }
        });

        if (!cancelled) {
          setQrCodeSrc(generatedQrCode);
        }
      } catch {
        if (!cancelled) {
          setError("Não foi possível renderizar o QR Code. Use o código PIX copia e cola.");
        }
      }
    }

    void resolveQrCode();

    return () => {
      cancelled = true;
    };
  }, [charge]);

  useEffect(() => {
    if (!open || !charge || phase !== "waiting") {
      return;
    }

    const updateRemainingTime = () => {
      const expiresAt = new Date(charge.expires_at).getTime();
      const fallbackExpiresAt = Date.now() + charge.expires_in * 1000;
      const effectiveExpiresAt = Number.isNaN(expiresAt) ? fallbackExpiresAt : expiresAt;
      const nextRemaining = Math.max(0, Math.ceil((effectiveExpiresAt - Date.now()) / 1000));

      setRemainingSeconds(nextRemaining);

      if (nextRemaining === 0) {
        setPhase("expired");
      }
    };

    updateRemainingTime();
    const interval = window.setInterval(updateRemainingTime, 1000);
    return () => window.clearInterval(interval);
  }, [charge, open, phase]);

  useEffect(() => {
    if (!open || !charge || phase !== "waiting") {
      return;
    }

    const eventSource = new EventSource(apiPath("/payments/status-stream"), {
      withCredentials: true
    });

    const handleStreamEvent = (
      rawData: string,
      fallbackEvent?: "payment_confirmed" | "payment_expired"
    ) => {
      const payload = parsePaymentEvent(rawData);
      const eventName = payload?.event ?? fallbackEvent;

      if (eventName === "payment_confirmed" && !confirmedRef.current) {
        confirmedRef.current = true;
        setPhase("confirmed");
        window.setTimeout(() => {
          onPaymentConfirmed();
        }, 350);
      }

      if (eventName === "payment_expired") {
        setPhase("expired");
      }
    };

    eventSource.onmessage = (event) => handleStreamEvent(event.data);
    eventSource.addEventListener("payment_confirmed", (event) => {
      handleStreamEvent((event as MessageEvent<string>).data, "payment_confirmed");
    });
    eventSource.addEventListener("payment_expired", (event) => {
      handleStreamEvent((event as MessageEvent<string>).data, "payment_expired");
    });
    eventSource.onerror = () => {
      setError("Conexão de confirmação instável. O sistema continuará tentando enquanto o QR estiver ativo.");
    };

    return () => eventSource.close();
  }, [charge, onPaymentConfirmed, open, phase]);

  async function handleCreateCharge() {
    setPhase("creating");
    setError(null);
    setCopyState("idle");

    try {
      const nextCharge = await createPixCharge();
      setCharge(nextCharge);
      setPhase("waiting");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar a cobrança PIX."
      );
      setPhase("error");
    }
  }

  async function handleCopyPixCode() {
    if (!charge?.pix_copy_paste) {
      return;
    }

    try {
      await navigator.clipboard.writeText(charge.pix_copy_paste);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setError("Não foi possível copiar automaticamente. Selecione o código manualmente.");
    }
  }

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/55 px-4 py-6 backdrop-blur-sm"
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="paywall-title"
        className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-md border border-paper/25 bg-paper shadow-paper"
      >
        <div className="flex items-start justify-between gap-4 border-b border-graphite/15 px-5 py-4 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase text-coral">Limite gratuito atingido</p>
            <h2 id="paywall-title" className="mt-1 font-display text-2xl font-semibold text-ink">
              Pague via PIX para continuar a análise
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="focus-ring flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-graphite/15 bg-white text-graphite transition hover:bg-fog"
            aria-label="Fechar modal de pagamento"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="grid gap-6 px-5 py-6 sm:px-6 lg:grid-cols-[1fr_19rem]">
          <div className="space-y-5">
            <div className="rounded-md border border-graphite/15 bg-white p-5 shadow-tool">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-ink text-paper">
                  <CreditCard className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <p className="font-semibold text-ink">
                    Você atingiu o limite de 3 análises gratuitas.
                  </p>
                  <p className="mt-2 text-sm leading-6 text-graphite/70">
                    A análise de {fileName ?? "currículo selecionado"} será iniciada
                    automaticamente após a confirmação do pagamento.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-graphite/15 bg-white p-4">
                <p className="text-xs font-semibold uppercase text-graphite/60">Valor avulso</p>
                <p className="mt-2 font-display text-3xl font-semibold text-ink">{amount}</p>
              </div>
              <div className="rounded-md border border-graphite/15 bg-white p-4">
                <p className="text-xs font-semibold uppercase text-graphite/60">Método</p>
                <p className="mt-2 flex items-center gap-2 font-display text-3xl font-semibold text-ink">
                  <QrCode className="h-7 w-7 text-teal" aria-hidden="true" />
                  PIX
                </p>
              </div>
            </div>

            {phase === "idle" || phase === "error" ? (
              <button
                type="button"
                onClick={handleCreateCharge}
                className="focus-ring inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-ink px-5 py-3 text-sm font-bold text-paper transition hover:bg-graphite"
              >
                <CreditCard className="h-5 w-5" aria-hidden="true" />
                Pagar e Analisar
              </button>
            ) : null}

            {phase === "creating" ? (
              <div className="flex items-center gap-3 rounded-md border border-teal/25 bg-teal/10 px-4 py-3 text-sm text-ink">
                <Loader2 className="h-5 w-5 animate-spin text-teal" aria-hidden="true" />
                Gerando cobrança PIX...
              </div>
            ) : null}

            {phase === "confirmed" ? (
              <div className="flex items-center gap-3 rounded-md border border-moss/25 bg-mint/40 px-4 py-3 text-sm font-semibold text-ink">
                <ShieldCheck className="h-5 w-5 text-moss" aria-hidden="true" />
                Pagamento confirmado. Iniciando análise automaticamente.
              </div>
            ) : null}

            {phase === "expired" ? (
              <div className="space-y-3 rounded-md border border-amber/35 bg-amber/10 px-4 py-3 text-sm text-ink">
                <p className="font-semibold">Este QR Code expirou sem confirmação de pagamento.</p>
                <button
                  type="button"
                  onClick={handleCreateCharge}
                  className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-amber/35 bg-white px-4 py-2 font-semibold text-ink transition hover:bg-paper"
                >
                  <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                  Gerar novo QR Code
                </button>
              </div>
            ) : null}

            {error ? (
              <div className="rounded-md border border-coral/30 bg-coral/10 px-4 py-3 text-sm text-ink">
                {error}
              </div>
            ) : null}
          </div>

          <aside className="rounded-md border border-graphite/15 bg-white p-4 shadow-tool">
            {charge ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-ink">QR Code PIX</p>
                  <span className="rounded-full border border-graphite/15 bg-paper px-3 py-1 text-xs font-semibold text-graphite/70">
                    {formatRemainingTime(remainingSeconds)}
                  </span>
                </div>

                <div className="flex aspect-square items-center justify-center rounded-md border border-graphite/15 bg-paper p-3">
                  {qrCodeSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={qrCodeSrc}
                      alt="QR Code PIX para pagamento"
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <QrCode className="h-24 w-24 text-graphite/35" aria-hidden="true" />
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase text-graphite/60">
                      Código copia e cola
                    </p>
                    <button
                      type="button"
                      onClick={handleCopyPixCode}
                      className="focus-ring inline-flex min-h-9 items-center gap-2 rounded-md border border-graphite/15 bg-paper px-3 py-2 text-xs font-semibold text-ink transition hover:bg-fog"
                    >
                      {copyState === "copied" ? (
                        <Check className="h-4 w-4 text-moss" aria-hidden="true" />
                      ) : (
                        <Copy className="h-4 w-4" aria-hidden="true" />
                      )}
                      {copyState === "copied" ? "Copiado" : "Copiar"}
                    </button>
                  </div>
                  <textarea
                    readOnly
                    value={charge.pix_copy_paste}
                    className="no-scrollbar h-28 w-full resize-none rounded-md border border-graphite/15 bg-paper p-3 font-mono text-xs leading-5 text-graphite focus:outline-none"
                    aria-label="Código PIX copia e cola"
                  />
                </div>
              </div>
            ) : (
              <div className="flex min-h-[26rem] flex-col items-center justify-center rounded-md border border-dashed border-graphite/20 bg-paper px-4 text-center">
                <QrCode className="h-14 w-14 text-graphite/30" aria-hidden="true" />
                <p className="mt-4 text-sm font-semibold text-ink">Checkout dentro do modal</p>
                <p className="mt-2 text-sm leading-6 text-graphite/65">
                  Clique em Pagar e Analisar para gerar o QR Code PIX.
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

function normalizeQrCodeSource(value: string | undefined) {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (trimmed.startsWith("data:image/") || trimmed.startsWith("http")) {
    return trimmed;
  }

  if (trimmed.startsWith("<svg")) {
    return `data:image/svg+xml;utf8,${encodeURIComponent(trimmed)}`;
  }

  const compactValue = trimmed.replace(/^base64,/, "").replace(/\s/g, "");
  const looksLikeBase64Image = compactValue.length > 100 && /^[A-Za-z0-9+/]+={0,2}$/.test(compactValue);

  return looksLikeBase64Image ? `data:image/png;base64,${compactValue}` : null;
}

function parsePaymentEvent(rawData: string): PaymentStreamEvent | null {
  try {
    return JSON.parse(rawData) as PaymentStreamEvent;
  } catch {
    return null;
  }
}

function formatCurrency(amountCents: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(amountCents / 100);
}

function formatRemainingTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = Math.max(0, totalSeconds % 60)
    .toString()
    .padStart(2, "0");

  return `${minutes}:${seconds}`;
}
