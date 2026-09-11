/**
 * Журнал прогонов: что происходило и чем кончилось.
 *
 * Причина падения показывается строкой, а не значком: «упал» без причины
 * отправляет человека в логи, которых у него нет.
 */
import { Badge, Table, Text } from '@mantine/core';

import type { RunRow } from '../../api/types';
import { num } from '../format';

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
    <Table.ScrollContainer minWidth={760}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>№</Table.Th>
            <Table.Th>Статус</Table.Th>
            <Table.Th>Начат</Table.Th>
            <Table.Th>Завершён</Table.Th>
            <Table.Th>Проекты</Table.Th>
            <Table.Th>Units: смета → факт</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((run) => (
            <Table.Tr key={run.id} data-run={run.id}>
              <Table.Td>{run.id}</Table.Td>
              <Table.Td>
                <Badge
                  variant="light"
                  color={STATUS_COLOR[run.status] ?? 'gray'}
                  data-status={run.status}
                >
                  {run.status}
                </Badge>
              </Table.Td>
              <Table.Td>{moment(run.started_at ?? run.created_at)}</Table.Td>
              <Table.Td>{moment(run.finished_at)}</Table.Td>
              <Table.Td>
                {run.projects_ok} из {run.projects_total}
                {run.projects_failed > 0 && (
                  <Text size="xs" c="red">
                    упало {run.projects_failed}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
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
