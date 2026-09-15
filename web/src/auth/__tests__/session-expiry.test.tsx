/**
 * Сессия, протухшая посреди работы.
 *
 * Случай найден живьём 15.09.2026: вкладку оставили открытой на ночь, утром в
 * шапке человек по-прежнему числился вошедшим, а в карточках экранов стояла
 * строка сервера «нужен действующий токен». Причина — проверка «кто я» шла
 * ОДИН раз, на монтировании: всё, что протухало после, до слоя входа не
 * доходило вовсе, и каждый экран печатал `401` как содержимое.
 *
 * Здесь проверяется не разметка, а сам договор: ответ `401` на любой запрос
 * после входа заканчивает сессию — с названной причиной и без повторов.
 */
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from '../../App';
import { ApiError, forgetToken, rememberToken, request, storedToken } from '../../api/client';
import { renderApp } from '../../test/render';

const ME = {
  email: 'clerk@test.local',
  full_name: 'Сотрудник',
  group: 'user',
  rights: ['read', 'run'],
};

/** Токен есть и «кто я» его принимает, а за данными сервер отвечает `401`. */
function serverWithExpiredToken(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = typeof input === 'string' ? input : input.toString();
      if (path === '/api/auth/me') {
        return new Response(JSON.stringify(ME), { status: 200 });
      }
      return new Response(JSON.stringify({ detail: 'нужен действующий токен' }), { status: 401 });
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('протухшая сессия', () => {
  it('человек с протухшим токеном оказывается на входе, а не в пустом каркасе', async () => {
    serverWithExpiredToken();
    rememberToken('вчерашний');
    renderApp(<App />);

    expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument();
  });

  it('причина названа: сессия истекла, а не «неверный пароль» и не молчание', async () => {
    serverWithExpiredToken();
    rememberToken('вчерашний');
    renderApp(<App />);

    await screen.findByRole('heading', { name: 'Вход' });
    expect(await screen.findByText('Сессия истекла, войдите заново')).toBeInTheDocument();
  });

  it('текст сервера про токен человеку не показывается', async () => {
    serverWithExpiredToken();
    rememberToken('вчерашний');
    renderApp(<App />);

    await screen.findByRole('heading', { name: 'Вход' });
    expect(screen.queryByText('нужен действующий токен')).not.toBeInTheDocument();
  });

  it('протухший токен выбрасывается, а не ждёт следующего запроса', async () => {
    serverWithExpiredToken();
    rememberToken('вчерашний');
    renderApp(<App />);

    await screen.findByRole('heading', { name: 'Вход' });
    await waitFor(() => expect(storedToken()).toBeNull());
  });

  it('на входе 401 означает неверный пароль, а не истёкшую сессию', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'неверная почта или пароль' }), { status: 401 }),
      ),
    );
    renderApp(<App />);

    await screen.findByRole('heading', { name: 'Вход' });
    await expect(
      request('/api/auth/login', { method: 'POST', body: {}, anonymous: true }),
    ).rejects.toBeInstanceOf(ApiError);

    expect(screen.queryByText('Сессия истекла, войдите заново')).not.toBeInTheDocument();
  });
});
