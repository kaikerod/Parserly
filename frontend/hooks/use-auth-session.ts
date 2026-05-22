"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getAuthSession, logout as requestLogout } from "@/lib/api";

export interface AuthSessionState {
  isAuthenticated: boolean;
  isLoadingAuth: boolean;
  authError: string | null;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuthSession(initialIsAuthenticated: boolean): AuthSessionState {
  const [isAuthenticated, setIsAuthenticated] = useState(initialIsAuthenticated);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const resolveSession = useCallback(async (signal?: AbortSignal) => {
    setIsLoadingAuth(true);
    setAuthError(null);

    try {
      const session = await getAuthSession({ signal });
      if (signal?.aborted) {
        return;
      }

      setIsAuthenticated(session.authenticated);
    } catch (error) {
      if (isAbortError(error) || signal?.aborted) {
        return;
      }

      if (error instanceof ApiError && error.status === 401) {
        setIsAuthenticated(false);
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
  }, []);

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

    try {
      await requestLogout();
    } catch (error) {
      if (error instanceof Error) {
        setAuthError(error.message);
      }
    } finally {
      setIsLoadingAuth(false);
    }
  }, []);

  return {
    isAuthenticated,
    isLoadingAuth,
    authError,
    refreshSession,
    logout
  };
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
