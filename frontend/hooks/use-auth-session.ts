"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getAuthSession, logout as requestLogout } from "@/lib/api";
import { ALL_FEATURES_PERMISSION } from "@/types/auth";
import type { AuthAccessLevel, AuthPermission } from "@/types/auth";

export interface AuthSessionState {
  isAuthenticated: boolean;
  isLoadingAuth: boolean;
  authError: string | null;
  accessLevel: AuthAccessLevel | null;
  permissions: AuthPermission[];
  hasFullAccess: boolean;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuthSession(initialIsAuthenticated: boolean): AuthSessionState {
  const [isAuthenticated, setIsAuthenticated] = useState(initialIsAuthenticated);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [accessLevel, setAccessLevel] = useState<AuthAccessLevel | null>(null);
  const [permissions, setPermissions] = useState<AuthPermission[]>([]);

  const clearAccessProfile = useCallback(() => {
    setAccessLevel(null);
    setPermissions([]);
  }, []);

  const resolveSession = useCallback(async (signal?: AbortSignal) => {
    setIsLoadingAuth(true);
    setAuthError(null);

    try {
      const session = await getAuthSession({ signal });
      if (signal?.aborted) {
        return;
      }

      setIsAuthenticated(session.authenticated);
      if (session.authenticated) {
        setAccessLevel(session.access_level ?? null);
        setPermissions(session.permissions ?? []);
      } else {
        clearAccessProfile();
      }
    } catch (error) {
      if (isAbortError(error) || signal?.aborted) {
        return;
      }

      if (error instanceof ApiError && error.status === 401) {
        setIsAuthenticated(false);
        clearAccessProfile();
        setAuthError(null);
        return;
      }

      setAuthError(
        error instanceof Error ? error.message : "Nao foi possivel confirmar sua sessao."
      );
    } finally {
      if (!signal?.aborted) {
        setIsLoadingAuth(false);
      }
    }
  }, [clearAccessProfile]);

  useEffect(() => {
    setIsAuthenticated(initialIsAuthenticated);

    const controller = new AbortController();
    void resolveSession(controller.signal);

    return () => {
      controller.abort();
    };
  }, [initialIsAuthenticated, resolveSession]);

  const refreshSession = useCallback(async () => {
    await resolveSession();
  }, [resolveSession]);

  const logout = useCallback(async () => {
    setIsLoadingAuth(true);
    setAuthError(null);
    setIsAuthenticated(false);
    clearAccessProfile();

    try {
      await requestLogout();
    } catch (error) {
      if (error instanceof Error) {
        setAuthError(error.message);
      }
    } finally {
      setIsLoadingAuth(false);
    }
  }, [clearAccessProfile]);

  return {
    isAuthenticated,
    isLoadingAuth,
    authError,
    accessLevel,
    permissions,
    hasFullAccess: permissions.includes(ALL_FEATURES_PERMISSION),
    refreshSession,
    logout
  };
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
