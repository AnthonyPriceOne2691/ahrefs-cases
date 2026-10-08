/**
 * Права экрана следуют за сервером без перезагрузки (Z44).
 *
 * Примеры приёмки поставки `rights-refresh`: M110 (отказ `403` перечитывает «кто я»), M111 (возврат
 * на вкладку — тоже), M112 (отказ самого «кто я» не зацикливает перечитывание).
 *
 * Проверяется договор слоя входа, а не разметка экрана: кнопка «Удалить проект» в карточке
 * спрашивает тот же `can('delete_projects')`, что и пробник ниже.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, forgetToken, rememberToken, request } from '../../api/client';
import type { WhoAmI } from '../../api/types';
import { AuthProvider, useAuth } from '../AuthProvider';

const WITH: WhoAmI = {
  email: 'engineer@test.local',
  full_name: 'Инженер',
  group: 'engineer',
  rights: ['read', 'delete_projects'],
};
const WITHOUT: WhoAmI = { ...WITH, rights: ['read'] };
const REFUSAL = 'нет права delete_projects: его выдаёт администратор';

/** Сервер: «кто я» отвечает тем, что вернёт `me`, а любой другой запрос — отказом `403`. */
function server(me: () => Response): string[] {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = typeof input === 'string' ? input : input.toString();
      calls.push(path);
      if (path === '/api/auth/me') return me();
      return new Response(JSON.stringify({ detail: REFUSAL }), { status: 403 });
    }),
  );
  return calls;
}

function answer(rights: WhoAmI): Response {
  return new Response(JSON.stringify(rights), { status: 200 });
}

function asked(calls: string[]): number {
  return calls.filter((path) => path === '/api/auth/me').length;
}

/** Пробник: показывает, можно ли удалять, и по кнопке спрашивает сервер о том, что под правом. */
function Probe() {
  const { can, user } = useAuth();
  const [said, setSaid] = useState('');
  if (!user) return <p>грузится</p>;
  const ask = () => {
    request('/api/projects/1/deletion').catch((error: unknown) => {
      setSaid(error instanceof ApiError ? error.message : 'сбой');
    });
  };
  return (
    <div>
      <p>{can('delete_projects') ? 'можно удалять' : 'удалять нельзя'}</p>
      <button type="button" onClick={ask}>
        Спросить
      </button>
      <p>{said}</p>
    </div>
  );
}

function signedIn() {
  rememberToken('свежий');
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

beforeEach(() => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
});

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('права следуют за сервером', () => {
  it('M110: отказ 403 перечитывает права, и кнопка пропадает без перезагрузки', async () => {
    let rights = WITH;
    server(() => answer(rights));
    signedIn();
    expect(await screen.findByText('можно удалять')).toBeInTheDocument();

    rights = WITHOUT;
    fireEvent.click(screen.getByRole('button', { name: 'Спросить' }));

    expect(await screen.findByText('удалять нельзя')).toBeInTheDocument();
    expect(screen.getByText(REFUSAL)).toBeInTheDocument();
  });

  it('M111: возврат на вкладку перечитывает права ещё до первого отказа', async () => {
    let rights = WITH;
    const calls = server(() => answer(rights));
    signedIn();
    await screen.findByText('можно удалять');

    rights = WITHOUT;
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(await screen.findByText('удалять нельзя')).toBeInTheDocument();
    expect(asked(calls)).toBe(2);
  });

  it('M112: отказ самого «кто я» не зацикливает перечитывание', async () => {
    let first = true;
    const calls = server(() => {
      if (!first) return new Response(JSON.stringify({ detail: REFUSAL }), { status: 403 });
      first = false;
      return answer(WITH);
    });
    signedIn();
    await screen.findByText('можно удалять');

    fireEvent.click(screen.getByRole('button', { name: 'Спросить' }));
    await waitFor(() => expect(asked(calls)).toBe(2));
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));

    expect(asked(calls)).toBe(2);
  });
});
