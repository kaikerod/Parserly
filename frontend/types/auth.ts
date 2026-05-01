export interface RequestMagicLinkResponse {
  message: string;
  expires_in: number;
  magic_link?: string | null;
}

export interface LogoutResponse {
  message: string;
}
