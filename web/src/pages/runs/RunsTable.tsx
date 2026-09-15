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
import { runWord } from '../status';

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

function moment(iso: string | null): string {
  if (!iso) return '—';
  const at = new Date(iso);
  return at.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

/** Ширина, за которую текст из базы не выходит. Колонки таблицы делят
 *  ширину экрана между собой, и одна длинная строка — трассировка из прогона,
 *  длинная почта — раздвигает свою колонку за счёт всех остальных. */
const CELL_WIDTH = 220;

/** Столько колонок в таблице. Раскрытие судеб занимает строку во всю ширину,
 *  и это число — единственное место, где ширина названа. */
const COLUMNS = 7;

/** Фон полосы по номеру ПРОГОНА в списке. */
function stripe(index: number): string | undefined {
  return index % 2 === 1 ? 'var(--mantine-color-default-hover)' : undefined;
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
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>№</Table.Th>
            <Table.Th ta="center">Статус</Table.Th>
            <Table.Th ta="center">Кто запустил</Table.Th>
            <Table.Th ta="center">Начат</Table.Th>
            <Table.Th ta="center">Завершён</Table.Th>
            <Table.Th ta="center">Проекты</Table.Th>
            <Table.Th ta="center">Units: смета → факт</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.flatMap((run, index) => [
            <Table.Tr key={run.id} data-run={run.id} bg={stripe(index)}>
              <Table.Td>{run.id}</Table.Td>
              <Table.Td ta="center">
                <Badge
                  variant="light"
                  color={STATUS_COLOR[run.status] ?? 'gray'}
                  data-status={run.status}
                >
                  {runWord(run.status)}
                </Badge>
              </Table.Td>
              {/* Журнал существует ради вопроса «кто это запускал», и ответ
                  обязан переживать увольнение: учётку удалили — человек
                  остаётся здесь с пометкой. */}
              <Table.Td ta="center" data-author={run.started_by}>
                <Text size="sm" maw={CELL_WIDTH} mx="auto" style={{ wordBreak: 'break-word' }}>
                  {run.started_by_name || `#${run.started_by}`}
                </Text>
                {run.started_by_deleted && (
                  <Text size="xs" c="dimmed" data-author-deleted="yes">
                    (удалён)
                  </Text>
                )}
              </Table.Td>
              <Table.Td ta="center">{moment(run.started_at ?? run.created_at)}</Table.Td>
              <Table.Td ta="center">{moment(run.finished_at)}</Table.Td>
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
              <Table.Td ta="center">
                {num(run.units_estimated)} → {num(run.units_actual)}
              </Table.Td>
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
