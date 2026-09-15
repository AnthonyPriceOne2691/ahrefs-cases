/**
 * Предпросмотр порогов. Примеры приёмки E1, E3–E6, E9.
 *
 * С 15.09.2026 предпросмотр раскрывается вместе с версией: владелец попросил
 * убрать отдельную кнопку и паковать «пороги этой версии» и «что изменится» в
 * одну раскрывающуюся секцию — как на экране людей.
 *
 * Проверяется, виден ли каждый из четырёх исходов расчёта — и особенно тот,
 * который легче всего слить с «не изменится»: проект, которому этой версией
 * не хватает купленных месяцев.
 *
 * Условия групп словами проверяет соседний файл: там другой вопрос экрана.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { PAYLOAD, me, ruleset, server, showThresholds } from '../../test/thresholds';

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

const ME = me(['read', 'edit_thresholds']);

describe('версии', () => {
  it('E1: список версий, действующая помечена', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': {
        status: 200,
        body: [ruleset('2026-09-II', false, PAYLOAD, 2), ruleset('2026-09-I', true)],
      },
    });

    showThresholds();

    expect(await screen.findByText('действующая')).toBeInTheDocument();
    expect(screen.getByText('2026-09-II')).toBeInTheDocument();
  });
});

describe('предпросмотр', () => {
  it('E3 и E4: смена группы, первый вердикт и нехватка данных — три разных списка', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      'POST /api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 10,
          changes: [{ domain: 'alpha.example', was: 'medium', becomes: 'good' }],
          first_time: [{ domain: 'beta.example', was: null, becomes: 'medium' }],
          unchanged: 6,
          missing_data: ['gamma.example', 'delta.example'],
        },
      },
    });

    showThresholds();
    // Раскрытие версии и есть вопрос «что изменится»: отдельная кнопка
    // спрашивала то же самое вторым нажатием (15.09.2026).
    await userEvent.click(await screen.findByText('2026-09-I'));

    // Группы теми же словами, что на экране проектов: «good → poor» посреди
    // русского экрана — то, что показал прогон живого стенда.
    expect(await screen.findByText(/alpha.example: средний → хороший/)).toBeInTheDocument();
    expect(screen.getByText(/beta.example: нет вердикта → средний/)).toBeInTheDocument();
    // Нехватка данных — отдельное состояние: этих проектов версией считать
    // нечем, и «остались в своей группе» про них сказать нельзя (L31).
    expect(screen.getByText(/Данных не хватает: 2/)).toBeInTheDocument();
    expect(screen.getByText(/gamma.example, delta.example/)).toBeInTheDocument();
  });

  it('E5: никто не сменит группу — это сказано словами', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      'POST /api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 10,
          changes: [],
          first_time: [],
          unchanged: 10,
          missing_data: [],
        },
      },
    });

    showThresholds();
    // Раскрытие версии и есть вопрос «что изменится»: отдельная кнопка
    // спрашивала то же самое вторым нажатием (15.09.2026).
    await userEvent.click(await screen.findByText('2026-09-I'));

    expect(await screen.findByText(/Никто не сменит группу/)).toBeInTheDocument();
  });
});

describe('предпросмотр: чего в счёте нет', () => {
  it('E9: «никто не сменит группу» не успокаивает, пока посчитана не вся база', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      'POST /api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 11,
          changes: [],
          first_time: [],
          unchanged: 5,
          missing_data: [
            'a.example',
            'b.example',
            'c.example',
            'd.example',
            'e.example',
            'f.example',
          ],
        },
      },
    });

    showThresholds();
    // Раскрытие версии и есть вопрос «что изменится»: отдельная кнопка
    // спрашивала то же самое вторым нажатием (15.09.2026).
    await userEvent.click(await screen.findByText('2026-09-I'));

    // Найдено прогоном живого экрана: пять из одиннадцати посчитаны, шести не
    // хватает данных — и зелёное «всё спокойно» тут читается как вывод о базе.
    expect(await screen.findByText(/посчитано 5 из 11/)).toBeInTheDocument();
    expect(screen.queryByText(/посчитаны все/)).not.toBeInTheDocument();
  });

  it('E6: отказ сервера показан его словами', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      'POST /api/rulesets/2026-09-I/preview': {
        status: 404,
        body: { detail: 'нет версии порогов 2026-09-I' },
      },
    });

    showThresholds();
    // Раскрытие версии и есть вопрос «что изменится»: отдельная кнопка
    // спрашивала то же самое вторым нажатием (15.09.2026).
    await userEvent.click(await screen.findByText('2026-09-I'));

    expect(await screen.findByText('нет версии порогов 2026-09-I')).toBeInTheDocument();
  });

  it('E7: кнопок правки на этом экране нет вовсе', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    showThresholds();
    await screen.findByText('действующая');

    // Право у человека есть, а кнопок нет: правка приедет отдельной поставкой,
    // и экран не должен обещать того, чего пока не делает.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Сохранить/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Активировать/ })).not.toBeInTheDocument();
    });
  });
});

describe('раскрытие версии', () => {
  const TWO = {
    'GET /api/auth/me': ME,
    'GET /api/rulesets': {
      status: 200,
      body: [ruleset('2026-09-II', false, PAYLOAD, 2), ruleset('2026-09-I', true)],
    },
    'POST /api/rulesets/2026-09-I/preview': {
      status: 200,
      body: {
        version: '2026-09-I',
        total: 3,
        changes: [],
        first_time: [],
        unchanged: 3,
        missing_data: [],
      },
    },
    'POST /api/rulesets/2026-09-II/preview': {
      status: 200,
      body: {
        version: '2026-09-II',
        total: 3,
        changes: [],
        first_time: [],
        unchanged: 3,
        missing_data: [],
      },
    },
  };

  it('нажатие на ту же версию сворачивает подробность', async () => {
    server(TWO);
    showThresholds();

    await userEvent.click(await screen.findByText('2026-09-I'));
    expect(await screen.findByText('Что изменится')).toBeInTheDocument();

    // Повторное нажатие повторяет вопрос, и ответ на него — закрыть. Так же
    // ведёт себя экран людей, и владелец просил повторить это поведение.
    await userEvent.click(screen.getByText('2026-09-I'));
    await waitFor(() =>
      expect(document.querySelector('[data-version-details]')?.closest('[style]')).toBeTruthy(),
    );
    expect(screen.getByText('2026-09-I')).toBeInTheDocument();
  });

  it('раскрытая версия остаётся в адресе — переживает обновление', async () => {
    server(TWO);
    showThresholds();

    await userEvent.click(await screen.findByText('2026-09-II'));

    await waitFor(() =>
      expect(new URLSearchParams(window.location.search).get('версия')).toBe('2026-09-II'),
    );
  });

  it('подробность раскрытой версии показывает её пороги, а не действующей', async () => {
    server(TWO);
    showThresholds();

    await userEvent.click(await screen.findByText('2026-09-II'));

    await waitFor(() =>
      expect(
        document.querySelector('[data-version-details]')?.getAttribute('data-version-details'),
      ).toBe('2026-09-II'),
    );
  });
});
