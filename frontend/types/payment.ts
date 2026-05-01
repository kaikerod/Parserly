export interface CreateChargeResponse {
  billing_id: string;
  pix_qr_code: string;
  pix_copy_paste: string;
  expires_at: string;
  expires_in: number;
  amount_cents: number;
}

export interface PaymentStreamEvent {
  event?: "payment_confirmed" | "payment_expired" | string;
  analysis_credits?: number;
}
