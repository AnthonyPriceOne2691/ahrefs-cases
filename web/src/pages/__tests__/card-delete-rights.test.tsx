/**
 * Право удалять отобрано, пока карточка открыта (Z44): кнопка пропадает, но отказ виден нажавшему.
 *
 * Пример приёмки M110 поставки `rights-refresh` — на настоящем блоке удаления карточки: человек
 * спросил «что уйдёт», сервер ответил `403`, права перечитаны. Блок остаётся с текстом отказа до
 * «Отмена» и только потом пропадает — иначе кнопка исчезала бы молча.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { renderApp } from '../../test/render';
import { DeleteProject } from '../card/DeleteProject';

const REFUSAL = 'нет права delete_projects: его выдаёт администратор';

function me(rights: string[]): Response {
  const body = { email: 'e@test.local', full_name: 'Инженер', group: 'engineer', rights };
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('удаление проекта: право отобрали посреди вопроса', () => {
  it('M110: отказ виден в блоке до «Отмена», потом кнопки нет', async () => {
    let rights = ['read', 'delete_projects'];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = typeof input === 'string' ? input : input.toString();
        if (path === '/api/auth/me') return me(rights);
        return new Response(JSON.stringify({ detail: REFUSAL }), { status: 403 });
      }),
    );
    rememberToken('свежий');
    renderApp(
      <AuthProvider>
        <DeleteProject projectId={7} domain="gone.example" onDeleted={() => undefined} />
      </AuthProvider>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Удалить проект' }));
    rights = ['read'];

    expect(await screen.findByText(REFUSAL)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Да, удалить' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Удалить проект' })).not.toBeInTheDocument(),
    );
  });
});
