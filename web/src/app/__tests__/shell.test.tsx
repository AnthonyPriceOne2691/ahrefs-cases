/**
 * Шапка: что остаётся на узком экране.
 *
 * Дефект, найденный показом на 400 px: высота `AppShell.Header` задана жёстко
 * (56 px), а четыре элемента справа в строку не влезали — перенос второй
 * строки наезжал на содержимое экрана. Ширину jsdom не считает, поэтому
 * проверяется **механизм**, которым это решено: почта помечена «видна от sm»,
 * а группа и выход такой пометки не имеют.
 */
import { screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../../auth/AuthProvider';
import { rememberToken, forgetToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { Shell } from '../Shell';

const ME = {
  email: 'clerk@test.local',
  full_name: 'Сотрудник',
  group: 'user',
  rights: ['read'],
};

beforeEach(() => {
  rememberToken('токен');
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(ME), { status: 200 })),
  );
});

afterEach(() => {
  forgetToken();
  vi.unstubAllGlobals();
});

function show() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <Shell>
          <div>содержимое</div>
        </Shell>
      </BrowserRouter>
    </AuthProvider>,
  );
}

describe('шапка', () => {
  it('E1: на узком экране почта скрыта, а выход и группа остаются', async () => {
    show();

    const email = await screen.findByText(ME.email);
    // Класс Mantine — и есть реализация «видно от sm»: он выключает элемент на
    // экранах уже брейкпоинта. Проверяем его, потому что ширины в jsdom нет.
    expect(email.className).toContain('visible-from-sm');
    // Группа отвечает «под кем я это вижу», выход нужен на чужом ноутбуке —
    // оба остаются на любой ширине.
    expect(screen.getByText(ME.group).className).not.toContain('visible-from');
    expect(screen.getByRole('button', { name: 'Выйти' }).className).not.toContain('visible-from');
  });

  it('E1: содержимое экрана на месте — шапка его не подменяет', async () => {
    show();

    expect(await screen.findByText('содержимое')).toBeInTheDocument();
  });
});

describe('меню помнит, где человек был', () => {
  it('пункт ведёт на адрес с фильтрами, а не на голый путь', async () => {
    // Состояние экранов живёт в адресе. Без памяти переход «Проекты → Кейсы →
    // Проекты» сбрасывал бы фильтры и страницу, хотя человек из раздела
    // никуда не уходил.
    window.history.replaceState({}, '', '/projects?group=good&page=2');
    show();

    const link = await screen.findByRole('link', { name: 'Проекты' });

    await waitFor(() => expect(link).toHaveAttribute('href', '/projects?group=good&page=2'));
  });

  it('незнакомый раздел ведёт на свой путь', async () => {
    window.history.replaceState({}, '', '/projects');
    show();

    expect(await screen.findByRole('link', { name: 'Кейсы' })).toHaveAttribute('href', '/cases');
  });
});
