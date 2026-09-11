/**
 * Кто вошёл и что ему можно.
 *
 * Права берутся списком из `/api/auth/me`, а **не выводятся из группы**: с Ф5.5
 * право выдаётся и лично, поверх группы, и меню по названию группы не показало
 * бы раздел тому, кому право выдали точечно.
 *
 * Выход по `401` живёт здесь же: протухший токен обязан приводить к форме
 * входа, а не к пустым таблицам без объяснения.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { ApiError, forgetToken, rememberToken, request, storedToken } from '../api/client';
import type { TokenResponse, WhoAmI } from '../api/types';

interface AuthState {
  user: WhoAmI | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (right: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WhoAmI | null>(null);
  const [loading, setLoading] = useState(Boolean(storedToken()));

  const logout = useCallback(() => {
    forgetToken();
    setUser(null);
  }, []);

  useEffect(() => {
    if (!storedToken()) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    request<WhoAmI>('/api/auth/me')
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((error: unknown) => {
        // Любой отказ на «кто я» означает «войдите заново»: токена нет, он
        // протух или учётку выключили. Показать при этом каркас с пустыми
        // экранами было бы хуже, чем форма входа.
        if (!cancelled) logout();
        if (!(error instanceof ApiError)) console.error('me failed', error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const token = await request<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    });
    rememberToken(token.access_token);
    setUser(await request<WhoAmI>('/api/auth/me'));
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login,
      logout,
      can: (right: string) => Boolean(user?.rights.includes(right)),
    }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth вне AuthProvider');
  return value;
}
