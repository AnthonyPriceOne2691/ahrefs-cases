/**
 * Экран «Пороги»: действующая версия словами. Примеры приёмки E1, E2, E5–E7.
 *
 * Проверяется то, ради чего экран есть: понятны ли условия без JSON. Цифру
 * утверждает Head of Link Building, а не инженер, — и она обязана стоять в
 * предложении, а не в пути `groups.good.org_traffic.growth_pct_min`.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { PAYLOAD, me, ruleset, server, showThresholds } from '../../test/thresholds';

const ME = me(['read', 'edit_thresholds']);

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

/** Подробности версии живут в раскрытии списка (15.09.2026): отдельная карточка
 *  «Действующая версия» дословно повторяла их и была снята. */
async function openVersion(version = '2026-09-I') {
  await userEvent.click(await screen.findByText(version));
}

describe('действующая версия', () => {
  it('E1: показывается та версия, по которой считаются вердикты', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': {
        status: 200,
        body: [ruleset('2026-09-II', false, PAYLOAD, 2), ruleset('2026-09-I', true)],
      },
    });

    showThresholds();
    await openVersion();

    // Свежая версия — не обязательно действующая: сохранение не активирует.
    expect(await screen.findByText(/Пороги версии 2026-09-I — действующей/)).toBeInTheDocument();
  });

  it('E2 и E8: условия групп словами, включая вилку «средних»', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    showThresholds();
    await openVersion();

    expect(await screen.findByText('Рост трафика от 100 %')).toBeInTheDocument();
    expect(screen.getByText('И при этом прирост не меньше 2 000 визитов')).toBeInTheDocument();
    expect(screen.getByText(/Подтверждающих метрик нужно 1 из 2/)).toBeInTheDocument();
    expect(screen.getByText('Рост трафика от 20 % до 100 %')).toBeInTheDocument();
    expect(
      screen.getByText('Сюда же попадает сильный рост в процентах при малом приросте в визитах'),
    ).toBeInTheDocument();
  });

  it('ноль в ограничителе — «не задано», а не порог, равный нулю', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    showThresholds();
    await openVersion();
    await screen.findByText('Рост трафика от 100 %');

    // «Конец периода не ниже пика на 0 %» читалось бы как работающее правило.
    expect(screen.getAllByText('не задано').length).toBe(2);
  });
});

describe('состояния экрана', () => {
  it('E5: версий нет — сказано, чем это грозит', async () => {
    server({ 'GET /api/auth/me': ME, 'GET /api/rulesets': { status: 200, body: [] } });

    showThresholds();

    expect(await screen.findByText(/классифицировать нечем/)).toBeInTheDocument();
  });

  it('E6: отказ сервера показан его словами', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': { status: 403, body: { detail: 'нужно право read' } },
    });

    showThresholds();

    expect(await screen.findByText('нужно право read')).toBeInTheDocument();
  });

  it('E7: нереализованная нормализация названа до того, как её попробуют', async () => {
    server({
      'GET /api/auth/me': ME,
      'GET /api/rulesets': {
        status: 200,
        body: [
          ruleset('2026-09-I', true, { ...PAYLOAD, duration: { normalize_after_months: 12 } }),
        ],
      },
    });

    showThresholds();
    await openVersion();

    // Версия с ненулевой нормализацией не пройдёт разбор на сервере. Сказать
    // об этом на экране дешевле, чем показать отказ после сохранения.
    expect(await screen.findByText(/нормализация.*не реализована/i)).toBeInTheDocument();
  });
});
