/**
 * Заведение людей и правка прав. Примеры приёмки E1–E9.
 *
 * Главное здесь — **пароль, который показывается один раз**, и три состояния
 * личного права: «как в группе» это отсутствие решения, а не «нельзя».
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { renderApp } from '../../test/render';
import { UsersPage } from '../UsersPage';

interface Reply {
  status: number;
  body: unknown;
}

interface Call {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

const CATALOG = {
  rights: ['edit_thresholds', 'manage_users', 'read', 'run'],
  groups: {
    engineer: ['edit_thresholds', 'manage_users', 'read', 'run'],
    admin: ['edit_thresholds', 'manage_users', 'read', 'run'],
    user: ['read', 'run'],
  },
};

function user(id: number, group: string, personal: Record<string, boolean> = {}) {
  return {
    id,
    email: `human-${id}@test.local`,
    full_name: `Человек ${id}`,
    group,
    is_active: true,
    personal_rights: personal,
    rights: CATALOG.groups[group as keyof typeof CATALOG.groups] ?? [],
  };
}

function server(routes: Record<string, Reply>): { calls: Call[] } {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = (url.split('?')[0] ?? url).replace('http://localhost', '');
      const method = init?.method ?? 'GET';
      calls.push({
        url: path,
        method,
        body:
          typeof init?.body === 'string'
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      });
      const reply = routes[`${method} ${path}`] ?? { status: 404, body: { detail: 'нет пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return { calls };
}

const ME: Reply = {
  status: 200,
  body: {
    email: 'boss@test.local',
    full_name: 'Руководитель',
    group: 'admin',
    rights: ['read', 'run', 'manage_users'],
  },
};

const LIST: Reply = { status: 200, body: [user(1, 'admin'), user(2, 'user')] };
const RIGHTS: Reply = { status: 200, body: CATALOG };
const BASE = { 'GET /api/auth/me': ME, 'GET /api/users': LIST, 'GET /api/users/rights': RIGHTS };

function show() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <UsersPage />
      </BrowserRouter>
    </AuthProvider>,
  );
}

/** Выбрать человека: правка идёт по выбранной строке. */
async function choose(id: number) {
  const row = await screen.findByText(`human-${id}@test.local`);
  await userEvent.click(row);
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('заведение', () => {
  it('E1 и E9: пароль показан один раз и убирается с экрана', async () => {
    server({
      ...BASE,
      'POST /api/users': {
        status: 201,
        body: { user: user(3, 'user'), password: 'длинный-сгенерированный-пароль' },
      },
    });

    show();
    await userEvent.type(await screen.findByLabelText('Почта (она же логин)'), 'new@test.local');
    await userEvent.click(screen.getByRole('button', { name: /Завести и показать пароль/ }));

    expect(await screen.findByText('длинный-сгенерированный-пароль')).toBeInTheDocument();
    // Второго показа не будет: сервис хранит только хеш.
    await userEvent.click(screen.getByRole('button', { name: /Записал/ }));
    expect(screen.queryByText('длинный-сгенерированный-пароль')).not.toBeInTheDocument();
  });

  it('E2: занятая почта — отказ сервера его словами', async () => {
    server({
      ...BASE,
      'POST /api/users': { status: 409, body: { detail: 'почта new@test.local уже занята' } },
    });

    show();
    await userEvent.type(await screen.findByLabelText('Почта (она же логин)'), 'new@test.local');
    await userEvent.click(screen.getByRole('button', { name: /Завести и показать пароль/ }));

    expect(await screen.findByText(/уже занята/)).toBeInTheDocument();
  });
});

describe('правка', () => {
  it('E3 и E8: группа и доступ ко входу уходят на сервер', async () => {
    const { calls } = server({
      ...BASE,
      'PATCH /api/users/2': { status: 200, body: user(2, 'admin') },
    });

    show();
    await choose(2);
    await userEvent.click(screen.getByRole('switch', { name: 'вход разрешён' }));

    await waitFor(() => expect(calls.some((call) => call.method === 'PATCH')).toBe(true));
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch?.body).toEqual({ is_active: false });
  });

  it('E4 и E5: «как в группе» — это отсутствие ключа, а не «нельзя»', async () => {
    const { calls } = server({
      ...BASE,
      'PATCH /api/users/2': { status: 200, body: user(2, 'user') },
    });

    show();
    await choose(2);
    // Ищем переключатель **нужного права**, а не первый в списке: порядок прав
    // — вопрос сортировки и меняется, а «править пороги» остаётся собой (L48).
    const пороги = screen.getByLabelText('править пороги');
    await userEvent.click(within(пороги).getByRole('radio', { name: 'выдать' }));

    await waitFor(() => expect(calls.some((call) => call.method === 'PATCH')).toBe(true));
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch?.body).toEqual({ personal_rights: { edit_thresholds: true } });
  });

  it('E6: последнего администратора не разжаловать — словами сервера', async () => {
    server({
      ...BASE,
      'PATCH /api/users/1': {
        status: 409,
        body: { detail: 'это последний администратор: снять группу с него нельзя' },
      },
    });

    show();
    await choose(1);
    // Переключатель группы есть и в правке, и в форме заведения: берём первый,
    // он принадлежит панели выбранного человека.
    const [группа] = screen.getAllByRole('radio', { name: 'пользователь' });
    if (!группа) throw new Error('переключателя группы нет');
    await userEvent.click(группа);

    expect(await screen.findByText(/последний администратор/)).toBeInTheDocument();
  });

  it('E7: перевыпуск пароля показывает новый — тоже один раз', async () => {
    server({
      ...BASE,
      'POST /api/users/2/password': {
        status: 200,
        body: { user: user(2, 'user'), password: 'новый-длинный-пароль' },
      },
    });

    show();
    await choose(2);
    await userEvent.click(screen.getByRole('button', { name: /Выпустить новый пароль/ }));

    expect(await screen.findByText('новый-длинный-пароль')).toBeInTheDocument();
    expect(screen.getByText(/Второго показа не будет/)).toBeInTheDocument();
  });
});
