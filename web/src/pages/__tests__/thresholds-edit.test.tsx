/**
 * Правка порогов. Примеры приёмки E1–E9.
 *
 * Главное, что здесь проверяется, — **разнесённость шагов**: сохранение не
 * применяет, применение спрашивает подтверждение, пересчёт отдельно. Слитые в
 * один шаг, они переложили бы всю базу по группам до того, как кто-то посмотрел
 * последствия.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import type { Call, Reply } from '../../test/thresholds';
import { me, ruleset, server, showThresholds } from '../../test/thresholds';

const PREVIEW = {
  version: '2026-09-II',
  total: 10,
  changes: [{ domain: 'alpha.example', was: 'medium', becomes: 'good' }],
  first_time: [],
  unchanged: 9,
  missing_data: [],
};

const LIST: Reply = { status: 200, body: [ruleset('2026-09-I', true)] };

/** Открыть форму и назвать версию — общее начало для всех шагов после первого. */
async function openForm(name = '2026-09-II') {
  await userEvent.click(await screen.findByRole('button', { name: 'Править пороги' }));
  await userEvent.type(screen.getByLabelText('Имя версии'), name);
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

const ME_EDIT = me(['read', 'edit_thresholds']);
const SAVED: Reply = { status: 201, body: ruleset('2026-09-II', false) };
const APPLIED: Reply = { status: 200, body: ruleset('2026-09-II', true) };

describe('доступ к форме', () => {
  it('E1: без права `edit_thresholds` формы нет вовсе', async () => {
    server({ 'GET /api/auth/me': me(['read']), 'GET /api/rulesets': LIST });

    showThresholds();
    await screen.findByText(/Действующая версия/);

    expect(screen.queryByRole('button', { name: 'Править пороги' })).not.toBeInTheDocument();
  });

  it('E2: поля заполнены значениями версии-основы', async () => {
    server({ 'GET /api/auth/me': ME_EDIT, 'GET /api/rulesets': LIST });

    showThresholds();
    await userEvent.click(await screen.findByRole('button', { name: 'Править пороги' }));

    // Правка начинается с утверждённых значений: пустая форма означала бы
    // пороги, взятые из воздуха.
    const проценты = screen.getAllByLabelText('Рост трафика от, %');
    expect(проценты[0]).toHaveValue('100');
    expect(проценты[1]).toHaveValue('20');
  });
});

describe('сохранение', () => {
  it('E3 и E4: версия создаётся неактивной, предпросмотр считается сам', async () => {
    const { calls } = server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': SAVED,
      'POST /api/rulesets/2026-09-II/preview': { status: 200, body: PREVIEW },
    });

    showThresholds();
    await openForm();
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));

    expect(await screen.findByText(/не действует/)).toBeInTheDocument();
    // Предпросмотр — тот самый цикл ТЗ: правишь цифру, видишь последствия.
    expect(await screen.findByText(/alpha.example: средний → хороший/)).toBeInTheDocument();
    expect(calls.some((call) => call.url.endsWith('/preview') && call.method === 'POST')).toBe(
      true,
    );
  });

  it('правка уходит в payload, а пустое поле — как «не задано»', async () => {
    const { calls } = server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': SAVED,
      'POST /api/rulesets/2026-09-II/preview': { status: 200, body: PREVIEW },
    });

    showThresholds();
    await openForm();
    const [ростХорошего] = screen.getAllByLabelText('Рост трафика от, %');
    const [приростХорошего] = screen.getAllByLabelText('Прирост не меньше, визитов');
    if (!ростХорошего || !приростХорошего) throw new Error('полей формы нет');
    await userEvent.clear(ростХорошего);
    await userEvent.type(ростХорошего, '60');
    await userEvent.clear(приростХорошего);
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));

    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true));
    const saved = calls.find((call) => call.url === '/api/rulesets' && call.method === 'POST');
    const payload = saved?.body?.payload as {
      groups: { good: { org_traffic: Record<string, unknown> } };
      windows: Record<string, unknown>;
    };
    expect(payload.groups.good.org_traffic).toMatchObject({
      growth_pct_min: 60,
      // Пустое поле — «не задано», а не ноль: ноль означал бы «прирост от нуля
      // визитов», то есть условие, пропускающее всех (урок L95).
      growth_abs_min: null,
    });
    // Непоказанное в форме переносится как есть, а не теряется.
    expect(payload.windows).toMatchObject({ point_a_months: 2, baseline: 'period' });
  });
});

describe('пустые поля', () => {
  it('пустое обязательное поле не уезжает на сервер, а выключаемое уходит нулём', async () => {
    const { calls } = server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': SAVED,
      'POST /api/rulesets/2026-09-II/preview': { status: 200, body: PREVIEW },
    });

    showThresholds();
    await openForm();
    const [рост] = screen.getAllByLabelText('Рост трафика от, %');
    const пик = screen.getByLabelText('Конец периода не ниже пика на, %');
    if (!рост) throw new Error('поля формы нет');
    await userEvent.clear(рост);

    // Найдено прогоном живого экрана: у этих полей в модели порогов нет
    // `None` — пустое значение вернулось бы `422` уже после сохранения.
    expect(screen.getByText(/Эти поля обязательны/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Сохранить версию/ })).toBeDisabled();

    await userEvent.type(рост, '60');
    await userEvent.clear(пик);
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));

    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true));
    const saved = calls.find((call) => call.url === '/api/rulesets' && call.method === 'POST');
    const payload = saved?.body?.payload as { guards: Record<string, unknown> };
    // Ноль, а не `null`: здесь ноль и означает «условие выключено».
    expect(payload.guards.end_vs_peak_min_pct).toBe(0);
  });

  it('E5: занятое имя версии — отказ сервера его словами', async () => {
    server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': {
        status: 409,
        body: { detail: 'версия 2026-09-II уже есть: правка порогов — это новая версия' },
      },
    });

    showThresholds();
    await openForm();
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));

    expect(await screen.findByText(/уже есть: правка порогов/)).toBeInTheDocument();
  });

  it('E6: кривая структура — `422` с именем поля', async () => {
    server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': {
        status: 422,
        body: { detail: 'groups.good.org_traffic.growth_pct_min: значение должно быть числом' },
      },
    });

    showThresholds();
    await openForm();
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));

    // Структуру проверяет сервер (`thresholds.parse`), и его текст называет
    // поле: вторая проверка на фронте разошлась бы с первой.
    expect(await screen.findByText(/growth_pct_min/)).toBeInTheDocument();
  });
});

describe('применение и пересчёт', () => {
  async function saveAndGetApplyButton(calls: Call[]) {
    await openForm();
    await userEvent.click(screen.getByRole('button', { name: /Сохранить версию/ }));
    const apply = await screen.findByRole('button', { name: 'Применить версию' });
    expect(calls.some((call) => call.url.endsWith('/activate'))).toBe(false);
    return apply;
  }

  it('E7: первое нажатие ничего не применяет, а спрашивает', async () => {
    const { calls } = server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': SAVED,
      'POST /api/rulesets/2026-09-II/preview': { status: 200, body: PREVIEW },
      'POST /api/rulesets/2026-09-II/activate': APPLIED,
    });

    showThresholds();
    const apply = await saveAndGetApplyButton(calls);
    await userEvent.click(apply);

    // Активация меняет группы для всех, кто откроет сервис после неё.
    expect(await screen.findByRole('button', { name: /Точно применить/ })).toBeInTheDocument();
    expect(calls.some((call) => call.url.endsWith('/activate'))).toBe(false);
  });

  it('E8 и E9: подтверждение применяет, пересчёт отчитывается строками', async () => {
    const { calls } = server({
      'GET /api/auth/me': ME_EDIT,
      'GET /api/rulesets': LIST,
      'POST /api/rulesets': SAVED,
      'POST /api/rulesets/2026-09-II/preview': { status: 200, body: PREVIEW },
      'POST /api/rulesets/2026-09-II/activate': APPLIED,
      'POST /api/rulesets/2026-09-II/recalc': {
        status: 200,
        body: { version: '2026-09-II', lines: ['пересчитано проектов: 10', 'сменили группу: 1'] },
      },
    });

    showThresholds();
    const apply = await saveAndGetApplyButton(calls);
    await userEvent.click(apply);
    await userEvent.click(screen.getByRole('button', { name: /Точно применить/ }));

    await waitFor(() => expect(calls.some((call) => call.url.endsWith('/activate'))).toBe(true));

    // Плашка знает, что версию применили: «пока не действует» после активации
    // — то, что показал прогон живого стенда.
    expect(await screen.findByText(/следующая классификация пойдёт по ней/)).toBeInTheDocument();

    // Применение не переписывает вердикты: пересчёт — отдельный шаг.
    await userEvent.click(await screen.findByRole('button', { name: 'Пересчитать вердикты' }));

    expect(await screen.findByText(/пересчитано проектов: 10/)).toBeInTheDocument();
  });
});
