/**
 * Заведение людей и правка прав. Примеры приёмки E1–E9.
 *
 * Главное здесь — **пароль, который показывается один раз**, и три состояния
 * личного права: решение, совпавшее с группой, не записывается вовсе — право
 * продолжает ехать за группой.
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

/** Открыть окно добавления: форма живёт в модалке, а не внизу страницы. */
async function openCreate() {
  await userEvent.click(await screen.findByRole('button', { name: 'Добавить пользователя' }));
}

/** Выбрать человека: правка идёт по выбранной **строке таблицы**.
 *
 * Именно по строке, а не по почте текстом: открытая панель показывает ту же
 * почту заголовком, и поиск по тексту находил бы два элемента — то есть
 * ломался бы ровно тогда, когда панель открыта. */
async function choose(id: number) {
  const row = await waitFor(() => {
    const found = document.querySelector(`[data-user="${id}"]`);
    if (!found) throw new Error(`строки человека ${id} нет`);
    return found;
  });
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
    await openCreate();
    await userEvent.type(await screen.findByLabelText('Почта (она же логин)'), 'new@test.local');
    await userEvent.click(screen.getByRole('button', { name: /Добавить и показать пароль/ }));

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
    await openCreate();
    await userEvent.type(await screen.findByLabelText('Почта (она же логин)'), 'new@test.local');
    await userEvent.click(screen.getByRole('button', { name: /Добавить и показать пароль/ }));

    expect(await screen.findByText(/уже занята/)).toBeInTheDocument();
  });
});

describe('окно добавления', () => {
  it('форма живёт в окне, а не на странице', async () => {
    // Форма внизу страницы всегда открыта, всегда пуста и занимает экран у
    // того, кто пришёл посмотреть права. Добавление — редкое действие, и у
    // него есть начало и конец.
    server(BASE);

    show();
    await screen.findByRole('button', { name: 'Добавить пользователя' });
    expect(screen.queryByLabelText('Почта (она же логин)')).toBeNull();

    await openCreate();
    expect(await screen.findByLabelText('Почта (она же логин)')).toBeInTheDocument();
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

describe('личные права поверх группы', () => {
  it('E4: «да» поверх группы записывается личным правом', async () => {
    const { calls } = server({
      ...BASE,
      'PATCH /api/users/2': { status: 200, body: user(2, 'user') },
    });

    show();
    await choose(2);
    // Ищем переключатель **нужного права**, а не первый в списке: порядок прав
    // — вопрос сортировки и меняется, а «править пороги» остаётся собой (L48).
    const пороги = screen.getByLabelText('править пороги');
    await userEvent.click(within(пороги).getByRole('radio', { name: 'Да' }));

    await waitFor(() => expect(calls.some((call) => call.method === 'PATCH')).toBe(true));
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch?.body).toEqual({ personal_rights: { edit_thresholds: true } });
  });

  it('E5: «нет» у права, которое даёт группа, записывается личным', async () => {
    const { calls } = server({
      ...BASE,
      'PATCH /api/users/2': { status: 200, body: user(2, 'user', { read: false }) },
    });

    show();
    await choose(2);
    await userEvent.click(
      within(screen.getByLabelText('смотреть данные')).getByRole('radio', { name: 'Нет' }),
    );

    await waitFor(() => expect(calls.some((call) => call.method === 'PATCH')).toBe(true));
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({
      personal_rights: { read: false },
    });
  });

  it('E5: возврат к тому, что даёт группа, стирает личное решение', async () => {
    // Иначе право приколачивается к человеку намертво: перевод в другую группу
    // его бы не тронул, а руководитель нажимал «да», а не «навсегда».
    const { calls } = server({
      ...BASE,
      'GET /api/users': { status: 200, body: [user(1, 'admin'), user(2, 'user', { read: false })] },
      'PATCH /api/users/2': { status: 200, body: user(2, 'user') },
    });

    show();
    await choose(2);
    await userEvent.click(
      within(screen.getByLabelText('смотреть данные')).getByRole('radio', { name: 'Да' }),
    );

    await waitFor(() => expect(calls.some((call) => call.method === 'PATCH')).toBe(true));
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({ personal_rights: {} });
  });

  it('переключатель сам встаёт по группе, а не по личным правам', async () => {
    // «Править пороги» группа `user` не даёт, а `admin` даёт — и экран обязан
    // показывать это без всякого личного решения.
    server({
      ...BASE,
      'GET /api/users': { status: 200, body: [user(1, 'admin'), user(2, 'user')] },
    });

    show();
    await choose(2);
    expect(
      within(screen.getByLabelText('править пороги')).getByRole('radio', { name: 'Нет' }),
    ).toBeChecked();
    expect(
      within(screen.getByLabelText('смотреть данные')).getByRole('radio', { name: 'Да' }),
    ).toBeChecked();

    await choose(2);
    await choose(1);
    expect(
      within(await screen.findByLabelText('править пороги')).getByRole('radio', { name: 'Да' }),
    ).toBeChecked();
  });
});

describe('раскрытие человека', () => {
  it('повторное нажатие сворачивает, чужое — переключает', async () => {
    // Само движение проверить нечем: в jsdom нет ни разметки, ни переходов, и
    // `Collapse` держит содержимое в DOM даже свёрнутым. Проверяется решение,
    // которое движением показывают: кто сейчас раскрыт.
    server(BASE);

    show();
    await choose(2);
    expect(document.querySelector('[data-user="2"]')).toHaveAttribute('data-selected', 'yes');

    // То же нажатие — свернуть: нажатие повторяет вопрос, ответ — закрыть.
    await choose(2);
    await waitFor(() =>
      expect(document.querySelector('[data-user="2"]')).toHaveAttribute('data-selected', 'no'),
    );

    // Чужое нажатие при открытой панели: текущая сворачивается, новая
    // открывается после неё — иначе содержимое подменяется под открытой
    // панелью и читается как подмена.
    await choose(2);
    await choose(1);
    await waitFor(() =>
      expect(document.querySelector('[data-user="2"]')).toHaveAttribute('data-selected', 'no'),
    );
    await waitFor(() =>
      expect(document.querySelector('[data-user="1"]')).toHaveAttribute('data-selected', 'yes'),
    );

    // И панель показывает уже этого человека: у админа «править пороги» — «да».
    expect(
      await within(await screen.findByLabelText('править пороги')).findByRole('radio', {
        name: 'Да',
      }),
    ).toBeChecked();
  });
});

describe('удаление пользователя', () => {
  it('спрашивает подтверждение и называет, что будет с журналом', async () => {
    // Удаление необратимо, а кнопка стоит рядом с переключателями прав, по
    // которым кликают часто. Подтверждение называет последствие, а не
    // действие: человек решает, что будет с журналом, а не «нажать ли».
    const { calls } = server({ ...BASE, 'DELETE /api/users/2': { status: 204, body: null } });

    show();
    await choose(2);
    await userEvent.click(screen.getByRole('button', { name: 'Удалить пользователя' }));

    expect(screen.getByText(/останутся в журнале/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: 'Да, удалить' }));

    await waitFor(() => expect(calls.some((call) => call.method === 'DELETE')).toBe(true));
  });

  it('отмена не удаляет', async () => {
    const { calls } = server({ ...BASE, 'DELETE /api/users/2': { status: 204, body: null } });

    show();
    await choose(2);
    await userEvent.click(screen.getByRole('button', { name: 'Удалить пользователя' }));
    await userEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(screen.queryByText(/останутся в журнале/)).toBeNull();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);
  });

  it('отказ сервера показан его словами', async () => {
    // Последний администратор и «удалять станет некому» — разные запреты с
    // разными причинами, и придумывать за сервер текст нельзя.
    server({
      ...BASE,
      'DELETE /api/users/2': {
        status: 409,
        body: { detail: 'это последний администратор: удалить его нельзя' },
      },
    });

    show();
    await choose(2);
    await userEvent.click(screen.getByRole('button', { name: 'Удалить пользователя' }));
    await userEvent.click(screen.getByRole('button', { name: 'Да, удалить' }));

    expect(await screen.findByText(/последний администратор/)).toBeInTheDocument();
  });
});
