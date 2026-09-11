/**
 * Вход и выход. Примеры приёмки E1, E2, E3, E7.
 *
 * Проверяется поведение, а не разметка: что видит не вошедший человек, что
 * происходит с токеном и что случается, когда сервер отвечает `401`.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from '../../App';
// Подписи ищутся по вхождению: у обязательного поля Mantine дорисовывает в
// label звёздочку, и точное совпадение «Почта» не находит ничего.
import { TOKEN_KEY, forgetToken } from '../../api/client';
import { renderApp } from '../../test/render';

interface Reply {
  status: number;
  body: unknown;
}

function server(routes: Record<string, Reply>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = typeof input === 'string' ? input : input.toString();
      const reply = routes[path] ?? { status: 404, body: { detail: 'нет такого пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
}

const ME = {
  email: 'clerk@test.local',
  full_name: 'Сотрудник',
  group: 'user',
  rights: ['read', 'run'],
};

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('вход', () => {
  it('E1: без токена человек видит форму входа, а не пустой каркас', async () => {
    server({});

    renderApp(<App />);

    expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument();
    expect(screen.queryByText('Проекты')).not.toBeInTheDocument();
  });

  it('E2: после входа токен сохраняется и человек попадает внутрь', async () => {
    server({
      '/api/auth/login': { status: 200, body: { access_token: 'свежий', rights: ME.rights } },
      '/api/auth/me': { status: 200, body: ME },
    });
    renderApp(<App />);

    await userEvent.type(await screen.findByLabelText(/Почта/), ME.email);
    await userEvent.type(screen.getByLabelText(/Пароль/), 'пароль-подлиннее');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByText(ME.email)).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBe('свежий');
  });

  it('E3: неверный пароль даёт одно сообщение без подсказок', async () => {
    server({ '/api/auth/login': { status: 401, body: { detail: 'неверная почта или пароль' } } });
    renderApp(<App />);

    await userEvent.type(await screen.findByLabelText(/Почта/), 'кто-то@test.local');
    await userEvent.type(screen.getByLabelText(/Пароль/), 'не тот');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByText('неверная почта или пароль')).toBeInTheDocument();
  });

  it('E7: протухший токен возвращает на форму входа, а не показывает пустые экраны', async () => {
    localStorage.setItem(TOKEN_KEY, 'протухший');
    server({ '/api/auth/me': { status: 401, body: { detail: 'нужен действующий токен' } } });

    renderApp(<App />);

    expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem(TOKEN_KEY)).toBeNull());
  });
});
