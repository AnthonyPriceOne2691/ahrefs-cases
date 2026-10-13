/**
 * Журнал прогонов: что происходило и чем кончилось.
 *
 * Причина падения показывается строкой, а не значком: «упал» без причины
 * отправляет человека в логи, которых у него нет. По той же причине рядом с
 * «17 из 19» живёт «пропущено 2» с раскрытием: пропуск — штатный исход, и
 * человеку важно, кого именно не собрали (требование ТЗ к логам прогона).
 */
import { Badge, Table, Text } from '@mantine/core';

import { useFoldedChoice } from '../../app/foldedChoice';
import type { RunRow } from '../../api/types';
import { num } from '../format';
import { runWord, stageWord, unitsNote } from '../status';

import { RunCases } from './RunCases';
import { FatesRow, WhySkipped } from './RunFates';

/** Цвет статуса. Исходов пять, и «частично» — не то же, что «готово». */
const STATUS_COLOR: Record<string, string> = {
  queued: 'gray',
  running: 'blue',
  done: 'teal',
  partial: 'yellow',
  failed: 'red',
  rejected: 'orange',
};

/** Дата и под ней время — двумя строками у каждого прогона, как номер и ступень:
 *  «13.10.2026, 12:10» одной строкой переносился там, где колонке не хватало
 *  места, и строка журнала меняла высоту (Z60). */
function Moment({ iso }: { iso: string | null }) {
  if (!iso) {
    return (
      <Table.Td ta="center">
        <Text size="sm">—</Text>
      </Table.Td>
    );
  }
  const at = new Date(iso);
  return (
    <Table.Td ta="center">
      <Text size="sm">{at.toLocaleDateString('ru-RU', { dateStyle: 'short' })}</Text>
      <Text size="xs" c="dimmed">
        {at.toLocaleTimeString('ru-RU', { timeStyle: 'short' })}
      </Text>
    </Table.Td>
  );
}

/** Ширина, за которую текст из базы не выходит. Колонки таблицы делят
 *  ширину экрана между собой, и одна длинная строка — трассировка из прогона,
 *  длинная почта — раздвигает свою колонку за счёт всех остальных. */
const CELL_WIDTH = 220;

/** Колонки журнала и их доли ширины, в сумме 100 %.
 *
 *  Доли задаёт таблица (`table-layout: fixed`), а не содержимое строк: пока цикл
 *  по файлу проходил ступени, колонка «№» раздувалась 112 → 169 px и сжимала
 *  соседей, таблица «плясала» (Z60, владелец 13.10.2026). Номеру отдано место под
 *  самую длинную ступень («цикл · данные под кейс»), статусу — под «частично». */
const HEADERS: readonly { title: string; share: number; center: boolean }[] = [
  { title: '№', share: 17, center: false },
  { title: 'Статус', share: 12, center: true },
  { title: 'Кто запустил', share: 18, center: true },
  { title: 'Начат', share: 10, center: true },
  { title: 'Завершён', share: 10, center: true },
  { title: 'Проекты', share: 10, center: true },
  { title: 'Units: смета → факт', share: 10, center: true },
  { title: 'Кейсы', share: 13, center: true },
];

/** Столько колонок в таблице. Раскрытие судеб занимает строку во всю ширину,
 *  и это число — единственное место, где ширина названа. */
const COLUMNS = HEADERS.length;

/** Фон полосы по номеру ПРОГОНА в списке. */
function stripe(index: number): string | undefined {
  return index % 2 === 1 ? 'var(--mantine-color-default-hover)' : undefined;
}

/** Ступень под номером. Цикл по файлу — одна строка на все ступени: какая идёт
 *  (или на какой он встал), видно здесь же, и строка короче «цикл по файлу ·
 *  данные под кейс» — та не помещалась в колонку и переносилась (Z60). */
function stageLine(run: RunRow): string {
  if (run.stage === 'cycle' && run.current_stage && run.status !== 'done') {
    return `цикл · ${stageWord(run.current_stage)}`;
  }
  return stageWord(run.stage);
}

/** Ступень — всегда одна строка; не поместилась (узкое окно) — многоточие, а не перенос. */
const STAGE_LINE = { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } as const;

/** Почта переносится после «@», а не посреди слова: колонка своей ширины (Z60),
 *  и «anthony@parsingprice / s.com» читалось хуже, чем «anthony@ / parsingprices.com». */
function Author({ name }: { name: string }) {
  const at = name.indexOf('@');
  if (at < 0) return name;
  return (
    <>
      {name.slice(0, at + 1)}
      <wbr />
      {name.slice(at + 1)}
    </>
  );
}

/** Номер и под ним ступень (B6). Не отдельной колонкой: число колонок держит
 *  строка раскрытия (`colSpan`), и таблица не должна раздаваться. Ступень — одной
 *  строкой: перенос менял высоту строки, пока цикл шёл. */
function RunNumber({ run }: { run: RunRow }) {
  return (
    <Table.Td>
      {run.id}
      {run.stage && (
        <Text size="xs" c="dimmed" data-stage={run.stage} style={STAGE_LINE}>
          {stageLine(run)}
        </Text>
      )}
    </Table.Td>
  );
}

/** Длинный статус («отклонён по квоте») переносится внутри значка, а не
 *  обрезается многоточием: колонка теперь своей ширины (Z60), и значок под неё
 *  не раздвигает. Отклонённый прогон своего статуса не меняет — высота его
 *  строки постоянна. */
const STATUS_LABEL = { label: { whiteSpace: 'normal' } } as const;

/** Статус значком. Ширину колонки держит её доля (`HEADERS`): колонка «Кейсы»
 *  забирала место у соседей, и «частично» обрезалось до «ЧАСТИ…» (браузер,
 *  25.09.2026). */
function RunStatus({ run }: { run: RunRow }) {
  return (
    <Table.Td ta="center">
      <Badge
        variant="light"
        color={STATUS_COLOR[run.status] ?? 'gray'}
        data-status={run.status}
        h="auto"
        maw="100%"
        styles={STATUS_LABEL}
      >
        {runWord(run.status)}
      </Badge>
    </Table.Td>
  );
}

/** Смета и факт, а у прогона без живого ключа — почему это не расход (Z38).
 *  Пометка в той же ячейке, не колонкой: число колонок держит раскрытие. */
function RunUnits({ run }: { run: RunRow }) {
  const note = unitsNote(run);
  return (
    <Table.Td ta="center">
      {num(run.units_estimated)} → {num(run.units_actual)}
      {note && (
        <Text size="xs" c="dimmed" maw={CELL_WIDTH} mx="auto" data-units-note={run.mode}>
          {note}
        </Text>
      )}
    </Table.Td>
  );
}

export function RunsTable({ rows }: { rows: RunRow[] }) {
  // Раскрыт всегда один прогон, и раскрытие держится в адресе: тот же хук, что
  // у людей и версий порогов.
  const { chosen, shown, choose } = useFoldedChoice('прогон');
  return (
    <Table.ScrollContainer minWidth={900}>
      {/* Чередование КРАСИТСЯ САМО, а не встроенным `striped`: тот считает
          строки DOM (`nth-of-type`), а раскрытие судеб вставляет между ними
          лишнюю — и все строки ниже меняли чётность, отчего соседние получали
          одинаковый фон (замечание владельца 15.09.2026). Полоса теперь
          принадлежит ПРОГОНУ, а не позиции строки, и раскрытие её не трогает. */}
      <Table layout="fixed">
        <Table.Thead>
          <Table.Tr>
            {HEADERS.map(({ title, share, center }) => (
              <Table.Th
                key={title}
                ta={center ? 'center' : undefined}
                style={{ width: `${share}%` }}
              >
                {title}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.flatMap((run, index) => [
            <Table.Tr key={run.id} data-run={run.id} bg={stripe(index)}>
              <RunNumber run={run} />
              <RunStatus run={run} />
              {/* Журнал существует ради вопроса «кто это запускал», и ответ
                  обязан переживать увольнение: учётку удалили — человек
                  остаётся здесь с пометкой. */}
              <Table.Td ta="center" data-author={run.started_by}>
                <Text size="sm" maw={CELL_WIDTH} mx="auto" style={{ wordBreak: 'break-word' }}>
                  <Author name={run.started_by_name || `#${run.started_by}`} />
                </Text>
                {run.started_by_deleted && (
                  <Text size="xs" c="dimmed" data-author-deleted="yes">
                    (удалён)
                  </Text>
                )}
              </Table.Td>
              <Moment iso={run.started_at ?? run.created_at} />
              <Moment iso={run.finished_at} />
              <Table.Td ta="center">
                {run.projects_ok} из {run.projects_total}
                {run.projects_failed > 0 && (
                  <Text size="xs" c="red">
                    упало {run.projects_failed}
                  </Text>
                )}
                <WhySkipped
                  runId={run.id}
                  skipped={run.projects_skipped}
                  failed={Boolean(run.error)}
                  opened={chosen === String(run.id)}
                  onToggle={() => choose(String(run.id))}
                />
              </Table.Td>
              <RunUnits run={run} />
              <RunCases run={run} />
            </Table.Tr>,
            <FatesRow
              key={`${run.id}-fates`}
              // Раскрытие в полосе своего прогона: иначе оно читается как
              // отдельная строка журнала, а не как продолжение этой.
              background={stripe(index)}
              runId={run.id}
              error={run.error}
              columns={COLUMNS}
              opened={chosen === String(run.id)}
              shown={shown === String(run.id)}
            />,
          ])}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
