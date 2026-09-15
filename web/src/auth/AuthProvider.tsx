/**
 * Кто вошёл и что ему можно.
 *
 * Права берутся списком из `/api/auth/me`, а **не выводятся из группы**: с Ф5.5
 * право выдаётся и лично, поверх группы, и меню по названию группы не показало
 * бы раздел тому, кому право выдали точечно.
 *
 * Выход по `401` живёт здесь же: протухший токен обязан приводить к форме
 * входа, а не к пустым таблицам без объяснения. До 15.09.2026 это исполнялось
 * ТОЛЬКО на монтировании — проверкой `/api/auth/me` один раз за загрузку
 * страницы. Вкладка, оставленная на ночь, ловила протухание уже после: «кто я»
 * больше не спрашивали, состояние «вы вошли» оставалось в памяти, а экраны
 * получали `401` и печатали его текстом в карточках. Теперь о конце сессии
 * сообщает сам клиент — из одного места и в любой момент жизни страницы.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ApiError,
  forgetToken,
  onSessionEnded,
  rememberToken,
  request,
  storedToken,
} from '../api/client';
import type { TokenResponse, WhoAmI } from '../api/types';

interface AuthState {
  user: WhoAmI | null;
  loading: boolean;
  /** Сессия оборвалась сама, а не по кнопке «Выйти». Форма входа скажет почему. */
  expired: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (right: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WhoAmI | null>(null);
  const [loading, setLoading] = useState(Boolean(storedToken()));
  const [expired, setExpired] = useState(false);

  const logout = useCallback(() => {
    forgetToken();
    setUser(null);
    // Ушёл по кнопке — объяснять нечего: человек сам так решил.
    setExpired(false);
  }, []);

  // Сессия кончилась посреди работы. Подписка живёт весь срок жизни провайдера:
  // протухнуть токен может на любом экране и в любую минуту, а не только на
  // первой загрузке.
  useEffect(() => {
    onSessionEnded(() => {
      setUser((previous) => {
        // Пометку ставим только тому, кто ДО этого считался вошедшим: `401` на
        // экране входа — это неверный пароль, и «сессия истекла» там соврало бы.
        if (previous) setExpired(true);
        return null;
      });
    });
    return () => onSessionEnded(null);
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
    setExpired(false);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      expired,
      login,
      logout,
      can: (right: string) => Boolean(user?.rights.includes(right)),
    }),
    [user, loading, expired, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth вне AuthProvider');
  return value;
}
