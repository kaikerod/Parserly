export type CategoryKey =
  | "keywords"
  | "formatting"
  | "structure"
  | "contact_info"
  | "quantifiable_achievements";

export type RecommendationPriority = "high" | "medium" | "low";

export interface CategoryReport {
  score: number;
  feedback: string;
}

export interface RecommendationReport {
  priority: RecommendationPriority;
  action: string;
  expected_impact: string;
}

export interface AnalysisReportPayload {
  overall_score: number;
  categories: Record<CategoryKey, CategoryReport>;
  recommendations: RecommendationReport[];
  detected_role: string | null;
}

export interface AnalysisResponse {
  id: string;
  filename: string;
  score: number;
  report_json: AnalysisReportPayload;
  model_used: string;
  created_at: string;
  analyses_used: number;
}

export interface AnalysisHistoryItem {
  id: string;
  filename: string;
  score: number;
  created_at: string;
  model_used: string;
}

export interface AnalysisHistoryResponse {
  items: AnalysisHistoryItem[];
  limit: number;
  offset: number;
  total: number;
}

export interface AnalysisQuotaResponse {
  authenticated: boolean;
  remaining_analyses: number;
  payment_required: boolean;
  registration_required: boolean;
  unlimited_analyses: boolean;
  message?: string | null;
}
