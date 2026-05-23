export interface RequestMagicLinkResponse {
  message: string;
  expires_in: number;
  magic_link?: string | null;
}

export interface AuthSessionResponse {
  authenticated: boolean;
  user_id?: string | null;
}

export interface GoogleOAuthCallbackResponse {
  message: string;
  user_id: string;
}

export interface LogoutResponse {
  message: string;
}
