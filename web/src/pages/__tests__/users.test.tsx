/**
 * Экран «Люди». Примеры приёмки E1–E6.
 *
 * Главное, что проверяется, — **происхождение права**. «Админ» в строке не
 * означает, что человеку можно всё, что даёт группа: право могли отобрать
 * лично. По названию группы этого не видно никак, и ради этого экран и нужен.
 */
import { screen } from '@testing-library/react';
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

const CATALOG = {
  rights: ['change_technical_settings', 'edit_thresholds', 'manage_users', 'read', 'run'],
  groups: {
    engineer: ['change_technical_settings', 'edit_thresholds', 'manage_users', 'read', 'run'],
    admin: ['edit_thresholds', 'manage_users', 'read', 'run'],
    user: ['read', 'run'],
  },
};

function user(
  id: number,
  group: string,
  personal: Record<string, boolean> = {},
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    email: `human-${id}@test.local`,
    full_name: `Человек ${id}`,
    group,
    is_active: true,
    personal_rights: personal,
    rights: CATALOG.groups[group as keyof typeof CATALOG.groups] ?? [],
    ...extra,
  };
}

function server(routes: Record<string, Reply>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = (url.split('?')[0] ?? url).replace('http://localhost', '');
      const reply = routes[path] ?? { status: 404, body: { detail: 'нет пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
}

const ME = {
  status: 200,
  body: {
    email: 'boss@test.local',
    full_name: 'Руководитель',
    group: 'admin',
    rights: ['read', 'run', 'manage_users'],
  },
};

const RIGHTS: Reply = { status: 200, body: CATALOG };

function show() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <UsersPage />
      </BrowserRouter>
    </AuthProvider>,
  );
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('список людей', () => {
  it('E1: строки с почтой, именем и группой', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 200, body: [user(1, 'admin'), user(2, 'user')] },
      '/api/users/rights': RIGHTS,
    });

    show();

    expect(await screen.findByText('human-1@test.local')).toBeInTheDocument();
    // Ищем в строках таблицы: слова «админ» и «пользователь» есть ещё и в
    // форме заведения, и общий поиск нашёл бы их там (переключатель группы).
    const строки = document.querySelectorAll('[data-user]');
    expect(строки).toHaveLength(2);
    expect(строки[0]?.querySelector('[data-group="admin"]')?.textContent).toBe('админ');
    expect(строки[1]?.querySelector('[data-group="user"]')?.textContent).toBe('пользователь');
  });

  it('E2: право, выданное лично поверх группы, помечено', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 200, body: [user(1, 'user', { edit_thresholds: true })] },
      '/api/users/rights': RIGHTS,
    });

    show();

    // Метка лежит внутри бейджа, а пометка происхождения — на самом бейдже.
    const право = (await screen.findByText('править пороги')).closest('[data-origin]');
    // Группа `user` порогов не даёт: право выдано точечно, и это видно.
    expect(право).toHaveAttribute('data-origin', 'выдано лично');
  });

  it('E3: право, отобранное у группы лично, помечено и зачёркнуто', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 200, body: [user(1, 'admin', { manage_users: false })] },
      '/api/users/rights': RIGHTS,
    });

    show();

    const право = (await screen.findByText('заводить людей')).closest('[data-origin]');
    // Ради этого случая экран и нужен: по названию группы его не видно.
    expect(право).toHaveAttribute('data-origin', 'отобрано лично');
    expect(право).toHaveStyle({ textDecoration: 'line-through' });
  });

  it('E4: выключенная учётка — человек заведён, но войти не может', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 200, body: [user(1, 'user', {}, { is_active: false })] },
      '/api/users/rights': RIGHTS,
    });

    show();

    expect(await screen.findByText('вход закрыт')).toBeInTheDocument();
  });
});

describe('состояния экрана', () => {
  it('E5: людей нет — сказано, чем это грозит', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 200, body: [] },
      '/api/users/rights': RIGHTS,
    });

    show();

    expect(await screen.findByText(/войти в сервис не может никто/)).toBeInTheDocument();
  });

  it('E6: отказ сервера показан его словами', async () => {
    server({
      '/api/auth/me': ME,
      '/api/users': { status: 403, body: { detail: 'нужно право manage_users' } },
      '/api/users/rights': RIGHTS,
    });

    show();

    expect(await screen.findByText('нужно право manage_users')).toBeInTheDocument();
  });
});
