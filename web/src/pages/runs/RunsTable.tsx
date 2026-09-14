/**
 * Журнал прогонов: что происходило и чем кончилось.
 *
 * Причина падения показывается строкой, а не значком: «упал» без причины
 * отправляет человека в логи, которых у него нет. По той же причине рядом с
 * «17 из 19» живёт «пропущено 2» с раскрытием: пропуск — штатный исход, и
 * человеку важно, кого именно не собрали (требование ТЗ к логам прогона).
 */
import { Badge, Table, Text } from '@mantine/core';

import type { RunRow } from '../../api/types';
import { num } from '../format';
import { runWord } from '../status';

import { RunFates } from './RunFates';

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

export function RunsTable({ rows }: { rows: RunRow[] }) {
  return (
    <Table.ScrollContainer minWidth={900}>
      <Table striped>
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
          {rows.map((run) => (
            <Table.Tr key={run.id} data-run={run.id}>
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
                <Text size="sm">{run.started_by_name || `#${run.started_by}`}</Text>
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
                <RunFates runId={run.id} skipped={run.projects_skipped} />
              </Table.Td>
              <Table.Td ta="center">
                {num(run.units_estimated)} → {num(run.units_actual)}
                {run.error && (
                  <Text size="xs" c="dimmed">
                    {run.error}
                  </Text>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
