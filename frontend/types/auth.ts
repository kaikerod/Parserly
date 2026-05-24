export const MASTER_ADMIN_ACCESS_LEVEL = "Administrador Master" as const;
export const STANDARD_USER_ACCESS_LEVEL = "Usuário Padrão" as const;
export const ALL_FEATURES_PERMISSION = "todas_as_funcionalidades" as const;
export const BASIC_FEATURES_PERMISSION = "funcionalidades_basicas" as const;

export type AuthAccessLevel =
  | typeof MASTER_ADMIN_ACCESS_LEVEL
  | typeof STANDARD_USER_ACCESS_LEVEL;

export type AuthPermission =
  | typeof ALL_FEATURES_PERMISSION
  | typeof BASIC_FEATURES_PERMISSION;

export interface RequestMagicLinkResponse {
  message: string;
  expires_in: number;
  magic_link?: string | null;
}

export interface AuthAccessProfile {
  access_level: AuthAccessLevel;
  permissions: AuthPermission[];
}

export interface AuthSessionResponse {
  authenticated: boolean;
  user_id?: string | null;
  access_level?: AuthAccessLevel | null;
  permissions?: AuthPermission[];
}

export interface GoogleOAuthCallbackResponse extends AuthAccessProfile {
  message: string;
  user_id: string;
}

export interface LogoutResponse {
  message: string;
}
