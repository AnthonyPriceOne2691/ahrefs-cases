/**
 * Карточка проекта. Примеры приёмки E1–E10.
 *
 * Проверяется не разметка, а то, ради чего экран существует: по нему должно
 * быть видно, **почему** группа именно такая, и числа обязаны совпадать с
 * вердиктом, а не считаться заново.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderScreen } from '../../test/render';
import { ProjectCardPage } from '../ProjectCardPage';

const PROJECT = {
  id: 7,
  domain: 'klinika.example',
  niche: 'медицина',
  geo: 'RU',
  service_type: 'seo',
  period_start: '2024-03-01',
  period_end: '2025-09-01',
  publishable: true,
  status: 'classified',
  group: 'good',
  score: 1400.4,
};

const VERDICT = {
  group: 'good',
  score: 1400.4,
  ruleset_version: '0.0.0-default',
  decided_at: '2026-09-11T10:00:00Z',
  reasons: [
    {
      subject: 'org_traffic',
      fact: 140,
      threshold: 50,
      passed: true,
      decisive: true,
      note: 'рост выше порога',
    },
    {
      subject: 'refdomains',
      fact: 12,
      threshold: 30,
      passed: false,
      decisive: false,
      note: '',
    },
  ],
  source: 'fixture',
  point_a: { org_traffic: 1000 },
  point_b: { org_traffic: 2400 },
  comparison: [
    {
      subject: 'org_traffic',
      label: 'органический трафик',
      before: 1000,
      after: 2400,
      absolute: 1400,
      pct: 140,
    },
    {
      subject: 'kw_top10',
      label: 'ключи в топ-10',
      before: 0,
      after: 25,
      absolute: 25,
      pct: null,
    },
  ],
};

const CHARTS = [
  { title: 'Динамика органического трафика', svg: '<svg data-test="traffic"></svg>' },
  { title: 'Динамика позиций', svg: '<svg data-test="positions"></svg>' },
];

/** Карточка читает номер проекта из адреса, поэтому рендерится маршрутом — так
 *  же, как в приложении. Без маршрута `useParams` пуст, и экран честно висит на
 *  «загружаем», а тест списывает это на медленный сервер. */
function renderCard() {
  return renderScreen(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectCardPage />} />
    </Routes>,
  );
}

/** Обычная карточка с вердиктом и графиками — заготовка почти для всех примеров.
 *  Повторять её в каждом тесте значит править восемь мест, когда изменится форма
 *  ответа. */
function cardServer(overrides: Record<string, { status: number; body: unknown }> = {}) {
  server({
    '/api/projects/7': {
      status: 200,
      body: {
        project: PROJECT,
        verdict: VERDICT,
        series: [],
        series_source: 'fixture',
        source_mismatch: null,
      },
    },
    '/api/projects/7/charts': { status: 200, body: CHARTS },
    ...overrides,
  });
}

function server(routes: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      // Сравниваем путь без параметров: у графиков появился `?grouping=…`, и
      // сопоставление целого адреса перестало находить маршрут.
      const path = url.split('?')[0] ?? url;
      const found = Object.entries(routes).find(([route]) => path.endsWith(route));
      const reply = found?.[1] ?? { status: 404, body: { detail: 'проекта 7 нет' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
}

beforeEach(() => {
  rememberToken('токен');
  window.history.pushState({}, '', '/projects/7');
});

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
  window.history.pushState({}, '', '/');
});

describe('карточка проекта: основание вердикта', () => {
  it('E1: шапка называет проект, группу, счёт и версию порогов', async () => {
    cardServer();

    renderCard();

    expect(await screen.findByText('klinika.example')).toBeInTheDocument();
    expect(screen.getByText('хороший')).toBeInTheDocument();
    // Счёт округляется, версия порогов стоит рядом: вердикт принадлежит версии,
    // и число без неё ничего не значит.
    expect(screen.getByText('счёт 1 400')).toBeInTheDocument();
    expect(screen.getByText('пороги 0.0.0-default')).toBeInTheDocument();
  });

  it('E2 и E10: таблица А → Б показывает числа вердикта', async () => {
    cardServer();

    renderCard();
    const row = await screen.findByText('органический трафик');

    const cells = [...(row.closest('tr')?.querySelectorAll('td') ?? [])].map((cell) =>
      // Разделитель разрядов у `toLocaleString('ru-RU')` — **неразрывный**
      // пробел: сравнение с обычным расходится невидимо глазу.
      cell.textContent?.replace(/\u00A0/g, ' '),
    );
    expect(cells).toEqual(['органический трафик', '1 000', '2 400', '+140 %']);
  });

  it('рост от нулевой базы не превращается в проценты', async () => {
    cardServer();

    renderCard();
    await screen.findByText('ключи в топ-10');

    // Сервер присылает `null`: рост с нуля формально бесконечен и по сути
    // ничего не значит. Подменить его «100 %» значило бы соврать.
    expect(screen.getByText('с нуля')).toBeInTheDocument();
  });

  it('E3: условия вердикта показаны с фактом, порогом и решающим', async () => {
    cardServer();

    renderCard();
    await screen.findByText('Почему эта группа');

    expect(screen.getByText('решающее')).toBeInTheDocument();
    expect(screen.getByText('прошло')).toBeInTheDocument();
    expect(screen.getByText('не прошло')).toBeInTheDocument();
  });

  it('E7: карточка предупреждает, когда числа и кривые из разных данных', async () => {
    // Таблица приходит из вердикта, кривые — из рядов. Когда это разные
    // данные, экран обязан сказать об этом раньше, чем человек сверит их
    // глазами: кейс по такому вердикту не собирается вовсе (Z10).
    cardServer({
      '/api/projects/7': {
        status: 200,
        body: {
          project: PROJECT,
          verdict: { ...VERDICT, source: 'fixture' },
          series: [],
          series_source: 'live',
          source_mismatch: 'вердикт вынесен по рядам «fixture», а показаны «live»',
        },
      },
    });

    renderCard();

    expect(await screen.findByText('Числа и кривые — из разных данных')).toBeInTheDocument();
    expect(screen.getByText(/вердикт вынесен по рядам/)).toBeInTheDocument();
  });

  it('обычная карточка ничем не предупреждает', async () => {
    cardServer();

    renderCard();
    await screen.findByText('органический трафик');

    expect(screen.queryByText('Числа и кривые — из разных данных')).toBeNull();
  });

  it('E4: графики приходят готовыми и вставляются как есть', async () => {
    cardServer();

    renderCard();
    await screen.findByText('Динамика позиций');

    expect(document.querySelector('[data-test="traffic"]')).not.toBeNull();
    expect(document.querySelector('[data-test="positions"]')).not.toBeNull();
  });
});

it('E8 и E9: тумблер перерисовывает кривые и не трогает вердикт', async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      urls.push(url);
      const body = url.includes('/charts')
        ? [
            {
              title: 'Динамика органического трафика',
              svg: `<svg data-step="${url.split('grouping=')[1]}"></svg>`,
            },
          ]
        : { project: PROJECT, verdict: VERDICT, series: [] };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );

  renderCard();
  await screen.findByText('Динамика органического трафика');
  await userEvent.click(screen.getByText('квартал'));

  await waitFor(() => expect(document.querySelector('[data-step="quarter"]')).not.toBeNull());
  // Вердикт принадлежит записи, а не виду экрана: таблица и условия те же.
  expect(screen.getByText('органический трафик')).toBeInTheDocument();
  expect(urls.filter((url) => url.includes('/api/projects/7?')).length).toBe(0);
});

describe('карточка проекта: состояния', () => {
  it('E5: без вердикта — что делать дальше, а не пустота', async () => {
    cardServer({
      '/api/projects/7': {
        status: 200,
        body: { project: { ...PROJECT, group: null, score: null }, verdict: null, series: [] },
      },
    });

    renderCard();

    expect(await screen.findByText(/Запустите классификацию/)).toBeInTheDocument();
  });

  it('E6: без рядов — карточка есть, кривых нет', async () => {
    cardServer({ '/api/projects/7/charts': { status: 200, body: [] } });

    renderCard();

    expect(await screen.findByText(/Кривых нет/)).toBeInTheDocument();
    expect(screen.getByText('klinika.example')).toBeInTheDocument();
  });

  it('E7: несуществующий проект назван словами', async () => {
    server({});

    renderCard();

    expect(await screen.findByText('проекта 7 нет')).toBeInTheDocument();
  });

  it('E8: отказ показан текстом сервера', async () => {
    server({
      '/api/projects/7': { status: 403, body: { detail: 'нет права read: группа user' } },
    });

    renderCard();

    expect(await screen.findByText(/нет права read/)).toBeInTheDocument();
  });

  it('E9: ссылка ведёт обратно к списку', async () => {
    cardServer();

    renderCard();
    await userEvent.click(await screen.findByText('← к списку проектов'));

    expect(window.location.pathname).toBe('/projects');
  });
});

describe('смена шага кривой', () => {
  /** Ответ по графикам держится, пока тест не разрешит его отдать: без паузы
   *  новые кривые приезжают в том же тике, и проверять «что видно во время
   *  загрузки» становится нечего. */
  function serverWithHeldCharts() {
    let release: (() => void) | null = null;
    let hold = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/charts')) {
          if (hold) {
            await new Promise<void>((resolve) => {
              release = resolve;
            });
          }
          const step = url.split('grouping=')[1] ?? 'month';
          return new Response(
            JSON.stringify([
              { title: 'Динамика органического трафика', svg: `<svg data-step="${step}"></svg>` },
            ]),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({
            project: PROJECT,
            verdict: VERDICT,
            series: [],
            series_source: 'fixture',
            source_mismatch: null,
          }),
          { status: 200 },
        );
      }),
    );
    return {
      holdNext: () => {
        hold = true;
      },
      let_go: () => {
        hold = false;
        release?.();
      },
    };
  }

  it('прежние кривые остаются на экране, пока едут новые', async () => {
    const net = serverWithHeldCharts();
    renderCard();
    await waitFor(() => expect(document.querySelector('[data-step="month"]')).not.toBeNull());

    net.holdNext();
    await userEvent.click(screen.getByText('квартал'));

    // Ядро дефекта: блок «Динамика» исчезал целиком, страница схлопывалась на
    // высоту одной строки, и браузер уводил прокрутку наверх — к кривым внизу
    // приходилось возвращаться руками.
    expect(document.querySelector('[data-step="month"]')).not.toBeNull();
    expect(screen.queryByText('Рисуем кривые…')).not.toBeInTheDocument();

    net.let_go();
    await waitFor(() => expect(document.querySelector('[data-step="quarter"]')).not.toBeNull());
  });

  it('переключатель не пропадает под пальцем, пока едут новые кривые', async () => {
    const net = serverWithHeldCharts();
    renderCard();
    await waitFor(() => expect(document.querySelector('[data-step="month"]')).not.toBeNull());

    net.holdNext();
    await userEvent.click(screen.getByText('квартал'));

    expect(screen.getByText('квартал')).toBeInTheDocument();
    expect(screen.getByText('месяц')).toBeInTheDocument();
    net.let_go();
  });

  it('подмена рисунка показана приглушением, а не молча', async () => {
    const net = serverWithHeldCharts();
    renderCard();
    await waitFor(() => expect(document.querySelector('[data-step="month"]')).not.toBeNull());

    net.holdNext();
    await userEvent.click(screen.getByText('год'));

    await waitFor(() => expect(document.querySelector('[data-stale]')).not.toBeNull());

    net.let_go();
    await waitFor(() => expect(document.querySelector('[data-step="year"]')).not.toBeNull());
    expect(document.querySelector('[data-stale]')).toBeNull();
  });
});

describe('кейс проекта на карточке', () => {
  const CASE_ROW = {
    id: 42,
    project_id: 7,
    domain: 'klinika.example',
    version: 1,
    anonymized: false,
    status: 'ready',
    created_at: '2026-09-12T10:00:00Z',
    filename: 'klinika.example Кейс.pdf',
    checksum: 'abc',
  };

  function cardWithCase(rows: unknown) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/api/cases')) {
          return new Response(JSON.stringify(rows), { status: 200 });
        }
        if (url.includes('/charts')) return new Response(JSON.stringify(CHARTS), { status: 200 });
        return new Response(
          JSON.stringify({
            project: PROJECT,
            verdict: VERDICT,
            series: [],
            series_source: 'fixture',
            source_mismatch: null,
          }),
          { status: 200 },
        );
      }),
    );
  }

  it('кнопка «Скачать PDF» доступна, когда файл есть', async () => {
    cardWithCase([CASE_ROW]);
    renderCard();

    const button = await screen.findByRole('button', { name: 'Скачать PDF' });
    await waitFor(() => expect(button).toBeEnabled());
  });

  it('кейс спрашивается по своему проекту, а не перебором библиотеки', async () => {
    cardWithCase([CASE_ROW]);
    renderCard();
    await screen.findByRole('button', { name: 'Скачать PDF' });

    const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const toCases = calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/cases'));
    expect(toCases.every((url) => url.includes('project_id=7'))).toBe(true);
  });

  it('кейса нет — кнопка не притворяется рабочей и говорит почему', async () => {
    cardWithCase([]);
    renderCard();

    const button = await screen.findByRole('button', { name: 'Скачать PDF' });
    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getByText(/Кейс ещё не собран/)).toBeInTheDocument();
  });

  it('кейс есть, а файла нет — это отдельная причина, и она названа', async () => {
    cardWithCase([{ ...CASE_ROW, filename: null, checksum: null }]);
    renderCard();

    const button = await screen.findByRole('button', { name: 'Скачать PDF' });
    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getByText(/файла к нему нет/)).toBeInTheDocument();
  });
});

describe('шаг, на котором рисовать нечего', () => {
  function cardWithEmptyQuarter() {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/charts')) {
          // На месяце кривые есть, на квартале — ни одной: у короткого периода
          // квартал схлопывается в одну точку, а кривой по одной точке не бывает.
          const step = url.split('grouping=')[1] ?? 'month';
          return new Response(JSON.stringify(step === 'month' ? CHARTS : []), { status: 200 });
        }
        if (url.includes('/api/cases')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(
          JSON.stringify({
            project: PROJECT,
            verdict: VERDICT,
            series: [],
            series_source: 'fixture',
            source_mismatch: null,
          }),
          { status: 200 },
        );
      }),
    );
  }

  it('переключатель остаётся, когда кривых нет — иначе это тупик', async () => {
    cardWithEmptyQuarter();
    renderCard();
    await screen.findByText('Динамика органического трафика');

    await userEvent.click(screen.getByText('квартал'));

    // Ядро дефекта: вместе с кривыми исчезал и переключатель, и вернуться на
    // месяц было нечем — выходили перезагрузкой страницы.
    expect(await screen.findByText('месяц')).toBeInTheDocument();
    expect(screen.getByText('год')).toBeInTheDocument();
  });

  it('причина названа по существу, а не «метрику не покупали»', async () => {
    cardWithEmptyQuarter();
    renderCard();
    await screen.findByText('Динамика органического трафика');

    await userEvent.click(screen.getByText('квартал'));

    // Ряды есть — их не хватает на этом шаге. Прежний текст про «не собрано»
    // отправлял бы человека докупать то, что уже куплено.
    expect(await screen.findByText(/точек слишком мало/)).toBeInTheDocument();
    expect(screen.queryByText(/не собрано/)).not.toBeInTheDocument();
  });

  it('вернуться на месяц можно, и кривые возвращаются', async () => {
    cardWithEmptyQuarter();
    renderCard();
    await screen.findByText('Динамика органического трафика');

    await userEvent.click(screen.getByText('квартал'));
    await screen.findByText(/точек слишком мало/);
    await userEvent.click(screen.getByText('месяц'));

    expect(await screen.findByText('Динамика органического трафика')).toBeInTheDocument();
  });
});

describe('таблица «Почему эта группа»', () => {
  const TWO_GROUPS = {
    ...VERDICT,
    reasons: [
      {
        subject: 'good.org_traffic_pct',
        fact: 341,
        threshold: 100,
        passed: true,
        decisive: true,
        note: 'рост органического трафика в процентах',
      },
      {
        subject: 'medium.org_traffic_pct',
        fact: 341,
        threshold: 20,
        passed: true,
        decisive: true,
        note: 'рост органического трафика в процентах',
      },
    ],
  };

  function cardWith(verdict: unknown) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/charts')) return new Response(JSON.stringify(CHARTS), { status: 200 });
        if (url.includes('/api/cases')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(
          JSON.stringify({
            project: PROJECT,
            verdict,
            series: [],
            series_source: 'fixture',
            source_mismatch: null,
          }),
          { status: 200 },
        );
      }),
    );
  }

  it('технических ключей правил на экране нет', async () => {
    cardWith(TWO_GROUPS);
    renderCard();

    await screen.findAllByText('рост органического трафика в процентах');
    expect(screen.queryByText('good.org_traffic_pct')).not.toBeInTheDocument();
    expect(screen.queryByText('medium.org_traffic_pct')).not.toBeInTheDocument();
  });

  it('одинаковые условия разных групп остаются различимыми', async () => {
    cardWith(TWO_GROUPS);
    renderCard();

    // Половина условий повторяется дважды — у «хорошего» и у «среднего», с
    // одной формулировкой и разными порогами. Различает их теперь заголовок
    // блока, а не слово в каждой строке: порог 100 стоит под «Условиями
    // хорошего», порог 20 — под «Условиями среднего».
    await screen.findAllByText('рост органического трафика в процентах');
    const good = document.querySelector('[data-conditions="good"]');
    const medium = document.querySelector('[data-conditions="medium"]');
    expect(good?.textContent).toContain('Условия хорошего');
    expect(medium?.textContent).toContain('Условия среднего');
    expect(good?.textContent).toContain('100');
    expect(medium?.textContent).toContain('20');
  });

  it('слово группы не повторяется в каждой строке', async () => {
    cardWith(TWO_GROUPS);
    renderCard();

    // Z26: колонка «Группа» писала одно и то же слово у каждого условия — у
    // `cleverfiles.com` шесть «хороший» подряд, потом пять «средний».
    // Владелец: «даже в плохих проектах выглядит странно».
    await screen.findAllByText('рост органического трафика в процентах');
    // Слово группы ищется ВНУТРИ блоков условий: в шапке карточки оно стоит
    // законно — там оно сказано один раз и про проект целиком.
    const conditions = [...document.querySelectorAll('[data-conditions]')];
    expect(conditions).toHaveLength(2);
    for (const block of conditions) {
      expect(block.textContent).not.toContain('Группа');
      expect(block.textContent).not.toContain('хороший');
      expect(block.textContent).not.toContain('средний');
    }
  });
});

/** Пустое место в колонке «Факт» — отдельная тема: это про деньги, а не про вид
 *  таблицы. Прочерк означал два разных случая, и заказчик спрашивает, какой
 *  именно (Z25). */
describe('пустой факт в таблице условий', () => {
  function cardWith(verdict: unknown) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/charts')) return new Response(JSON.stringify(CHARTS), { status: 200 });
        if (url.includes('/api/cases')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(
          JSON.stringify({
            project: PROJECT,
            verdict,
            series: [],
            series_source: 'fixture',
            source_mismatch: null,
          }),
          { status: 200 },
        );
      }),
    );
  }

  it('пустой факт говорит, не покупали или не отдали', async () => {
    // Z25: прочерк означал два разных случая, и разница в деньгах — «не
    // покупали» можно докупить, «нет данных» докупать нечем. Вопрос владельца
    // на `callmefred.com`: «а где мы фиксируем, покупали мы ссылки или нет?»
    cardWith({
      ...VERDICT,
      reasons: [
        {
          subject: 'good.refdomains_pct',
          fact: null,
          threshold: 30,
          passed: false,
          decisive: false,
          note: 'рост ссылающихся доменов',
          fact_missing: 'not_bought',
        },
        {
          subject: 'good.kw_top10_pct',
          fact: null,
          threshold: 15,
          passed: false,
          decisive: false,
          note: 'рост числа ключей в топ-10',
          fact_missing: 'no_data',
        },
      ],
    });
    renderCard();

    expect(await screen.findByText('не покупали')).toBeInTheDocument();
    expect(screen.getByText('нет данных')).toBeInTheDocument();
  });

  it('без ответа журнала экран не выдумывает причину', async () => {
    // Страж от перегиба: `fact_missing` не пришёл — значит журнал расхода про
    // домен молчит (данные старше журнала). Прочерк честнее догадки.
    cardWith({
      ...VERDICT,
      reasons: [
        {
          subject: 'good.refdomains_pct',
          fact: null,
          threshold: 30,
          passed: false,
          decisive: false,
          note: 'рост ссылающихся доменов',
        },
      ],
    });
    renderCard();

    await screen.findByText('рост ссылающихся доменов');
    expect(screen.queryByText('не покупали')).not.toBeInTheDocument();
    expect(screen.queryByText('нет данных')).not.toBeInTheDocument();
  });
});
