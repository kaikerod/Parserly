import type {
  AnalysisHistoryResponse,
  AnalysisQuotaResponse,
  AnalysisResponse
} from "@/types/analysis";
import type { AuthSessionResponse, LogoutResponse, RequestMagicLinkResponse } from "@/types/auth";
import type { CreateChargeResponse } from "@/types/payment";

const API_PREFIX = "/api/v1";
const CANONICAL_APP_ORIGIN = "https://www.parserly.com.br";

interface RequestOptions {
  signal?: AbortSignal;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly retryAfter: number | null;

  constructor(message: string, status: number, detail?: unknown, retryAfter?: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter ?? null;
  }
}

export function apiPath(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_PREFIX}${normalizedPath}`;
}

export function googleOAuthStartPath() {
  return publicAppPath(apiPath("/auth/google/start"));
}

function publicAppPath(path: string) {
  if (typeof window === "undefined" || isLocalBrowserOrigin(window.location.origin)) {
    return path;
  }

  return new URL(path, CANONICAL_APP_ORIGIN).toString();
}

function isLocalBrowserOrigin(origin: string) {
  try {
    const { hostname } = new URL(origin);
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
}

export async function requestMagicLink(email: string): Promise<RequestMagicLinkResponse> {
  const response = await fetch(apiPath("/auth/request-link"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify({ email }),
    credentials: "include"
  });

  return parseJsonResponse<RequestMagicLinkResponse>(
    response,
    "Não foi possível enviar o link de acesso."
  );
}

export async function getAuthSession(options: RequestOptions = {}): Promise<AuthSessionResponse> {
  const response = await fetch(apiPath("/auth/session"), {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store",
    signal: options.signal
  });

  return parseJsonResponse<AuthSessionResponse>(
    response,
    "Nao foi possivel confirmar sua sessao."
  );
}

export async function logout(): Promise<LogoutResponse> {
  const response = await fetch(apiPath("/auth/logout"), {
    method: "POST",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store"
  });

  return parseJsonResponse<LogoutResponse>(response, "Não foi possível encerrar a sessão.");
}

export async function submitResumeForAnalysis(file: File): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(apiPath("/analysis"), {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  return parseJsonResponse<AnalysisResponse>(
    response,
    "Não foi possível concluir a análise."
  );
}

export async function listAnalyses(
  limit = 10,
  offset = 0,
  options: RequestOptions = {}
): Promise<AnalysisHistoryResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset)
  });
  const response = await fetch(apiPath(`/analysis?${params.toString()}`), {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store",
    signal: options.signal
  });

  return parseJsonResponse<AnalysisHistoryResponse>(
    response,
    "Não foi possível carregar o histórico de análises."
  );
}

export async function getAnalysisById(
  id: string,
  options: RequestOptions = {}
): Promise<AnalysisResponse> {
  const response = await fetch(apiPath(`/analysis/${encodeURIComponent(id)}`), {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store",
    signal: options.signal
  });

  return parseJsonResponse<AnalysisResponse>(
    response,
    "Não foi possível abrir a análise salva."
  );
}

export async function deleteAnalysisById(
  id: string,
  options: RequestOptions = {}
): Promise<void> {
  const response = await fetch(apiPath(`/analysis/${encodeURIComponent(id)}`), {
    method: "DELETE",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store",
    signal: options.signal
  });

  await parseEmptyResponse(response, "NÃ£o foi possÃ­vel excluir a anÃ¡lise salva.");
}

export async function getAnalysisQuota(options: RequestOptions = {}): Promise<AnalysisQuotaResponse> {
  const response = await fetch(apiPath("/analysis/quota"), {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    credentials: "include",
    cache: "no-store",
    signal: options.signal
  });

  return parseJsonResponse<AnalysisQuotaResponse>(
    response,
    "Nao foi possivel verificar sua quota de analises."
  );
}

export async function createPixCharge(): Promise<CreateChargeResponse> {
  const response = await fetch(apiPath("/payments/create-charge"), {
    method: "POST",
    headers: {
      Accept: "application/json"
    },
    credentials: "include"
  });

  return parseJsonResponse<CreateChargeResponse>(
    response,
    "Não foi possível gerar a cobrança PIX."
  );
}

async function parseJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson(response);

  if (!response.ok) {
    throw new ApiError(
      extractErrorMessage(payload, fallbackMessage),
      response.status,
      payload,
      parseRetryAfter(response.headers.get("Retry-After"))
    );
  }

  return payload as T;
}

async function parseEmptyResponse(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok) {
    return;
  }

  const payload = await readJson(response);
  throw new ApiError(
    extractErrorMessage(payload, fallbackMessage),
    response.status,
    payload,
    parseRetryAfter(response.headers.get("Retry-After"))
  );
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractErrorMessage(payload: unknown, fallbackMessage: string) {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (isRecord(payload)) {
    const detail = payload.detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (isRecord(detail) && typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }

    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
  }

  return fallbackMessage;
}

function parseRetryAfter(value: string | null) {
  if (!value) {
    return null;
  }

  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) ? seconds : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
