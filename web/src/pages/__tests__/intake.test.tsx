/**
 * ВНИМАНИЕ: с 15.09.2026 «Загрузка» и «Прогоны» — один раздел, и приём списка
 * живёт на `RunsPage`. Проверки ниже про приём списка и смету; журнал прогонов
 * проверяет `ops.test.tsx`.
 *
 * Экран загрузки. Примеры приёмки E3–E12.
 *
 * Проверяется поведение, а не разметка: что человек видит после приёма, что
 * ему говорят при отказе и — главное — что кнопка запуска недоступна, когда
 * смета этого не позволяет. Цена ошибки здесь units заказчика, а не неудобство.
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { RunsPage } from '../RunsPage';
import { FILE_CSV, FILE_FORMAT, SHEET_ACCESS } from '../intake/ListHelp';

/** Раздел живёт в маршрутизаторе: признак открытого окна сметы держится в
 *  адресе, и без `Router` экран падает на `useLocation`. */
/** Смета живёт в окне (15.09.2026): плашка на странице пролистывалась вместе
 *  с ней, а смета — это решение «запускать ли», а не сводка. */
async function openEstimate() {
  await userEvent.click(await screen.findByRole('button', { name: 'Смета и запуск' }));
  await screen.findByRole('dialog');
}

function showRuns() {
  return renderApp(
    <BrowserRouter>
      <RunsPage />
    </BrowserRouter>,
  );
}

interface Reply {
  status: number;
  body: unknown;
}

const OK_ESTIMATE = {
  projects: 10,
  units_estimated: 1980,
  requests_planned: 10,
  requests_cached: 2,
  scheme_lines: ['organic-traffic-history: историей, 10 проектов, 1980 units'],
  quota_left: 9500,
  quota_reserved: 0,
  verdict: 'ok',
  may_start: true,
  reason: '',
};

const REPORT = {
  origin: 'список.xlsx',
  accepted: 10,
  created: 10,
  updated: 0,
  rejected_rows: 0,
  by_reason: {},
  rejections: [],
  notices: [],
};

/** Ответы по пути запроса. Очередь на путь — чтобы второй запрос той же сметы
 *  мог ответить иначе: ровно это и значит «смета пересчиталась».
 *
 *  Ключ можно писать с методом (`'GET /api/runs'`). Это понадобилось, когда
 *  приём списка и журнал прогонов сошлись в одном разделе: запуск — это
 *  `POST /api/runs`, журнал — `GET /api/runs`, и помощник, сличавший только
 *  путь, отдавал журналу ответ запуска. Падало это не на сравнении, а глубже —
 *  `(rows ?? []).some is not a function`, то есть в коде экрана, который в этом
 *  не виноват. Ключ без метода по-прежнему отвечает на любой. */
function server(routes: Record<string, Reply | Reply[]>): { calls: string[] } {
  const calls: string[] = [];
  const queues = { ...routes };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = typeof input === 'string' ? input : input.toString();
      const method = (init?.method ?? 'GET').toUpperCase();
      calls.push(path);
      // Побеждает САМОЕ ДЛИННОЕ совпадение, а не первое: `GET /api/runs`
      // (журнал) — префикс `/api/runs/estimate` (смета), и поиск «первого
      // подходящего» отдавал смете ответ журнала. Ошибка вылезала далеко от
      // причины: `quota_left.toLocaleString of undefined` в отрисовке.
      const route = (key: string) => {
        const [head, ...rest] = key.split(' ');
        return rest.length > 0
          ? { method: head, prefix: rest.join(' ') }
          : { method: null, prefix: key };
      };
      const candidates = Object.entries(queues).filter(([key]) => {
        const { method: only, prefix } = route(key);
        return (only === null || only === method) && path.startsWith(prefix);
      });
      // Длина ПУТИ, а не ключа: метод в ключе добавляет символов, и `GET
      // /api/runs` (журнал) обходил `/api/runs/7` (карточка прогона) просто
      // потому, что строка длиннее.
      candidates.sort(([a], [b]) => route(b).prefix.length - route(a).prefix.length);
      const found = candidates[0];
      if (!found) return new Response(JSON.stringify({ detail: 'нет пути' }), { status: 404 });
      const value = found[1];
      const reply = Array.isArray(value) ? (value.length > 1 ? value.shift() : value[0]) : value;
      return new Response(JSON.stringify(reply?.body), { status: reply?.status ?? 200 });
    }),
  );
  return { calls };
}

async function upload(file = new File(['x'], 'список.xlsx')) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  // `applyAccept: false`: подсказка `accept` фильтрует список в диалоге, но не
  // запрещает выбрать «все файлы» — отказ сервера по формату достижим, и
  // именно его проверяет E5.
  //
  // Второго нажатия здесь больше нет: с 15.09.2026 выбор файла и есть отправка.
  // Прежде кнопка стояла недоступной, пока файл не выбран, и выглядела
  // сломанной — владелец так её и описал.
  await userEvent.upload(input, file, { applyAccept: false });
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('экран загрузки', () => {
  it('E3: принятый файл показан числами, а не «готово»', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': { status: 200, body: REPORT },
    });

    showRuns();
    await upload();

    expect(await screen.findByText('принято 10')).toBeInTheDocument();
    expect(screen.getByText('создано 10')).toBeInTheDocument();
    expect(screen.getByText('обновлено 0')).toBeInTheDocument();
  });

  it('E4: отклонённые строки названы номером и причиной', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 200,
        body: {
          ...REPORT,
          accepted: 9,
          created: 9,
          rejected_rows: 1,
          by_reason: { bad_date: 1 },
          rejections: [{ row_no: 12, field: 'period_start', reason: 'bad_date', detail: '31.02' }],
          notices: [],
        },
      },
    });

    showRuns();
    await upload();

    // Номер строки — тот, который человек ищет глазами в Excel.
    expect(await screen.findByText('12')).toBeInTheDocument();
    expect(screen.getByText('дата не разобрана')).toBeInTheDocument();
  });

  it('E9: принятые с замечаниями показаны отдельно от отклонённых', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 200,
        body: {
          ...REPORT,
          notices: [
            { row_no: 2, field: 'work_volume', reason: 'bad_number', detail: '214 ссылок' },
          ],
        },
      },
    });

    showRuns();
    await upload();

    // Проект принят: отклонённых строк нет, а непонятая ячейка названа.
    expect(await screen.findByText('принято 10')).toBeInTheDocument();
    expect(screen.queryByText(/отклонено строк/)).not.toBeInTheDocument();
    expect(screen.getByText('Принято с замечаниями')).toBeInTheDocument();
    expect(screen.getByText('214 ссылок')).toBeInTheDocument();
    expect(screen.getByText('с замечаниями 1')).toBeInTheDocument();
  });
});

describe('экран загрузки: отказы источника', () => {
  it('E5: отказ по формату показывается текстом сервера', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 400,
        body: { detail: 'не понимаю формат файла: отчёт.pdf. Ожидаю .xlsx или .csv' },
      },
    });

    showRuns();
    await upload(new File(['x'], 'отчёт.pdf'));

    expect(await screen.findByText(/не понимаю формат файла/)).toBeInTheDocument();
  });

  it('E6 и E7: ссылка на закрытую таблицу объясняет, что чинить', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/link': {
        status: 400,
        body: { detail: 'таблица недоступна по ссылке: откройте доступ «по ссылке»' },
      },
    });

    showRuns();
    await userEvent.type(
      screen.getByLabelText(/Ссылка на Google Sheet/),
      'https://docs.google.com/spreadsheets/d/abc/edit',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Загрузить по ссылке' }));

    expect(await screen.findByText(/таблица недоступна по ссылке/)).toBeInTheDocument();
  });
});

describe('экран загрузки: смета и запуск', () => {
  it('E8: смета видна числами и разбивкой', async () => {
    rememberToken('токен');
    server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });

    showRuns();
    await openEstimate();

    expect(await screen.findByText('units по смете 1980')).toBeInTheDocument();
    expect(screen.getByText(/Остаток квоты: 9\s?500/)).toBeInTheDocument();
    expect(screen.getByText(/organic-traffic-history/)).toBeInTheDocument();
  });

  it('E9: не хватает квоты — кнопка недоступна, причина видна', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': {
        status: 200,
        body: {
          ...OK_ESTIMATE,
          quota_left: 300,
          verdict: 'not_enough',
          may_start: false,
          reason: 'не хватает units: остаток 300, нужно 1980, неснижаемый запас 500',
        },
      },
    });

    showRuns();
    await openEstimate();

    expect(await screen.findByText(/не хватает units: остаток 300/)).toBeInTheDocument();
    expect(screen.getByTestId('start-run')).toBeDisabled();
  });

  it('E10: «остаток неизвестен» — своя причина, а не «мало квоты»', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': {
        status: 200,
        body: {
          ...OK_ESTIMATE,
          quota_left: null,
          verdict: 'unknown',
          may_start: false,
          reason: 'остаток квоты Ahrefs неизвестен. Прогон не начат: «не знаем» значит «не тратим»',
        },
      },
    });

    showRuns();
    await openEstimate();

    expect(await screen.findByText(/остаток квоты Ahrefs неизвестен/)).toBeInTheDocument();
    expect(screen.getByText('Остаток квоты: неизвестен')).toBeInTheDocument();
    expect(screen.getByTestId('start-run')).toBeDisabled();
  });
});

describe('экран загрузки: прогон', () => {
  it('E11: запуск показывает номер прогона и его состояние', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/runs/7': {
        status: 200,
        body: {
          id: 7,
          status: 'done',
          projects_total: 10,
          projects_ok: 10,
          projects_failed: 0,
          units_estimated: 1980,
          units_actual: 1975,
          error: '',
        },
      },
      // Журнал и запуск — один путь, разные методы: без явного ключа журнал
      // получал бы ответ запуска (см. докстроку `server`).
      'GET /api/runs': { status: 200, body: [] },
      '/api/runs': { status: 202, body: { run_id: 7, queued_as: 'inline:7' } },
    });

    showRuns();
    await openEstimate();
    await userEvent.click(await screen.findByTestId('start-run'));

    expect(await screen.findByText(/Прогон №7/)).toBeInTheDocument();
  });

  it('E12: активный прогон отвечает отказом с его номером', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      'GET /api/runs': { status: 200, body: [] },
      '/api/runs': { status: 409, body: { detail: 'прогон 4 уже идёт: второй стоит вторую цену' } },
    });

    showRuns();
    await openEstimate();
    await userEvent.click(await screen.findByTestId('start-run'));

    expect(await screen.findByText(/прогон 4 уже идёт/)).toBeInTheDocument();
  });

  it('E13: после приёма смета пересчитывается — список изменился, цена другая', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': [
        { status: 200, body: { ...OK_ESTIMATE, projects: 0, units_estimated: 0 } },
        { status: 200, body: OK_ESTIMATE },
      ],
      '/api/intake/file': { status: 200, body: REPORT },
    });

    showRuns();
    await openEstimate();
    expect(await screen.findByText('units по смете 0')).toBeInTheDocument();
    await upload();

    await waitFor(() => expect(screen.getByText('units по смете 1980')).toBeInTheDocument());
  });
});

describe('вторая кнопка: шаг 2 и данные под кейс (B6)', () => {
  it('B6: вторая кнопка — смета кандидатов и запуск шага 2', async () => {
    rememberToken('токен');
    const { calls } = server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/runs/stage2/estimate': {
        status: 200,
        body: {
          ...OK_ESTIMATE,
          projects: 3,
          units_estimated: 470,
          requests_planned: 9,
          requests_cached: 0,
          scheme_lines: ['данные под кейс посчитаны по всем кандидатам — это верхняя граница'],
        },
      },
      '/api/runs/12': {
        status: 200,
        body: {
          id: 12,
          status: 'done',
          projects_total: 3,
          projects_ok: 3,
          projects_failed: 0,
          units_estimated: 470,
          units_actual: 410,
          error: '',
        },
      },
      'GET /api/runs': { status: 200, body: [] },
      'POST /api/runs/stage2': { status: 202, body: { run_id: 12, queued_as: 'inline:12' } },
    });

    showRuns();
    await userEvent.click(await screen.findByRole('button', { name: 'Дособрать кандидатов' }));
    const dialog = await screen.findByRole('dialog');

    // Число — кандидатов, а не всех проектов: смета второй кнопки про них.
    expect(await within(dialog).findByText('кандидатов 3')).toBeInTheDocument();
    // Данные под кейс — верхняя граница, и окно обязано так и сказать.
    expect(within(dialog).getByText(/верхняя граница/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Запустить шаг 2' }));

    expect(await within(dialog).findByText(/Прогон №12/)).toBeInTheDocument();
    expect(calls).toContain('/api/runs/stage2');
  });
});

describe('кнопка загрузки файла', () => {
  it('доступна до того, как файл выбран: она и открывает выбор', async () => {
    rememberToken('токен');
    server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });
    showRuns();
    await openEstimate();

    // Ядро жалобы: кнопка «по сути ничего не делает». Она была `disabled`,
    // пока файл не выбран, а выбирало его поле рядом — то есть работу делало
    // поле, а кнопка только подтверждала уже сделанное.
    expect(await screen.findByRole('button', { name: 'Загрузить файл' })).toBeEnabled();
  });

  it('поле показывает имя выбранного файла и в него нельзя печатать', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': { status: 200, body: REPORT },
    });
    showRuns();
    await openEstimate();
    await screen.findByRole('button', { name: 'Загрузить файл' });

    await upload(new File(['x'], 'сентябрь.xlsx'));

    const field = await screen.findByLabelText('Файл со списком');
    expect(field).toHaveValue('сентябрь.xlsx');
    expect(field).toHaveAttribute('readonly');
  });
});

/** `later` стоит в документе после `earlier`. */
function follows(earlier: Element, later: Element): boolean {
  return Boolean(earlier.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('отказ целиком — у своего поля', () => {
  const REFUSED = 'Файл «список.csv» не подходит: нет колонок period_start, geo.';

  it('V16: отказ по файлу — красная плашка под полем файла, отчёта нет', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': { status: 400, body: { detail: REFUSED } },
    });
    showRuns();

    await upload(new File(['x'], 'список.csv'));

    const refusal = await screen.findByText(REFUSED);
    // Под полем файла и НАД полем ссылки: отказ стоит там, где список давали.
    expect(follows(screen.getByLabelText('Файл со списком'), refusal)).toBe(true);
    expect(follows(refusal, screen.getByLabelText('Ссылка на Google Sheet'))).toBe(true);
    expect(screen.queryByText(/Принято из/)).not.toBeInTheDocument();
  });

  it('V17: отказ по ссылке — плашка под полем ссылки, а не под файлом', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/link': {
        status: 400,
        body: { detail: 'Таблица по ссылке не подходит: нет колонок client, owner.' },
      },
    });
    showRuns();

    await userEvent.type(
      screen.getByLabelText('Ссылка на Google Sheet'),
      'https://docs.google.com/spreadsheets/d/abc/edit#gid=7',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Загрузить по ссылке' }));

    const refusal = await screen.findByText(/Таблица по ссылке не подходит/);
    expect(follows(screen.getByLabelText('Ссылка на Google Sheet'), refusal)).toBe(true);
    expect(screen.queryByText(/Принято из/)).not.toBeInTheDocument();
  });

  it('V22: файл больше 2 МБ — отказ у поля, и на сервер он не уходит', async () => {
    // Сервер тоже отказал бы (413), но через прокси его ответ не доходит: он
    // рвёт соединение, не дочитав тело, и прокси отвечает «500» (замер в Chrome).
    rememberToken('токен');
    const { calls } = server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });
    showRuns();

    await upload(new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'выгрузка.csv'));

    const refusal = await screen.findByText(/«выгрузка.csv» больше 2 МБ/);
    expect(follows(screen.getByLabelText('Файл со списком'), refusal)).toBe(true);
    expect(calls.filter((path) => path.startsWith('/api/intake'))).toEqual([]);
  });

  it('V20: после выбора поле выбора пустеет — тот же файл можно выбрать снова', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': { status: 400, body: { detail: REFUSED } },
    });
    showRuns();

    await upload(new File(['x'], 'список.csv'));
    await screen.findByText(REFUSED);

    // Браузер не шлёт `change`, если выбран тот же файл, что уже стоит в поле:
    // список, поправленный после отказа, иначе не уходит вовсе — кнопка
    // молчит. Пустое поле выбора — условие того, что выбор сработает снова.
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.value).toBe('');
    expect(input.files).toHaveLength(0);
  });
});

describe('справка о таблице', () => {
  it('значок стоит у поля ссылки и назван словами', async () => {
    rememberToken('токен');
    server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });
    showRuns();

    // Знак вопроса сам по себе не говорит, о чём спросят: подпись обязательна,
    // и по ней же его находит тест.
    const help = await screen.findByLabelText('какой должна быть таблица');
    expect(help).toBeInTheDocument();
  });

  it('V18: у поля файла свой «?», названный словами', async () => {
    rememberToken('токен');
    server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });
    showRuns();

    // Карточку не раскрываем: попап Mantine в jsdom открывался здесь двадцать
    // две секунды (замер этой поставки, урок L76). Что в ней нарисовано —
    // проверяют данные ниже, `tests/test_intake_list_format.py` и браузер.
    expect(await screen.findByLabelText('каким должен быть файл')).toBeInTheDocument();
    expect(screen.getByLabelText('какой должна быть таблица')).toBeInTheDocument();
  });

  it('V18: про файл сказано, какие форматы, какой лист, разделитель и кодировка', () => {
    expect(FILE_FORMAT).toMatch(/XLSX/);
    expect(FILE_FORMAT).toMatch(/CSV/);
    expect(FILE_FORMAT).toMatch(/2 МБ/);
    expect(FILE_FORMAT).toMatch(/первый лист/);
    expect(FILE_CSV).toMatch(/точка с запятой/);
    expect(FILE_CSV).toMatch(/Windows-1251/);
    // Абзац про доступ по ссылке — у таблицы; файлу он ни к чему.
    expect(`${FILE_FORMAT} ${FILE_CSV}`).not.toMatch(/по ссылке|Авторизация/);
  });

  it('справка прямо говорит, что авторизация не нужна, а приватная таблица не годится', () => {
    // Два вопроса владельца одним предложением: он спросил и про формат, и про
    // авторизацию — значит по экрану это было не видно.
    expect(SHEET_ACCESS).toMatch(/Авторизация не нужна/);
    expect(SHEET_ACCESS).toMatch(/по ссылке/);
    expect(SHEET_ACCESS).toMatch(/приватную/i);
  });
});
