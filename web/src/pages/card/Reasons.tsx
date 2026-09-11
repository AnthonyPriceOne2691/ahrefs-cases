/**
 * Условия вердикта — то, чего в кейсе нет вовсе.
 *
 * Кейс показывает результат клиенту, карточка объясняет сотруднику, **почему**
 * группа такая: какой факт с каким порогом сравнили и какое условие оказалось
 * решающим. Без этого число на экране приходится принимать на веру.
 */
import { Badge, Group, Stack, Table, Text } from '@mantine/core';

import type { ReasonRow } from '../../api/types';
import { num } from '../format';

export function Reasons({ rows }: { rows: ReasonRow[] }) {
  if (rows.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Условия вердикта не записаны: версия порогов старше, чем эта запись.
      </Text>
    );
  }
  return (
    <Stack gap="xs">
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Условие</Table.Th>
            <Table.Th>Факт</Table.Th>
            <Table.Th>Порог</Table.Th>
            <Table.Th>Итог</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={`${row.subject}-${row.note}`} data-subject={row.subject}>
              <Table.Td>
                {/* Сверху человеческая формулировка, снизу ключ правила: ключ
                    нужен, когда сверяют с версией порогов, но читают строку
                    ради смысла, а не ради имени поля. */}
                <Group gap="xs">
                  <Text size="sm">{row.note || row.subject}</Text>
                  {row.decisive && (
                    <Badge size="xs" variant="light" data-decisive="true">
                      решающее
                    </Badge>
                  )}
                </Group>
                {row.note && (
                  <Text size="xs" c="dimmed">
                    {row.subject}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>{row.fact === null ? '—' : num(row.fact)}</Table.Td>
              <Table.Td>{row.threshold === null ? '—' : num(row.threshold)}</Table.Td>
              <Table.Td data-passed={row.passed}>{row.passed ? 'прошло' : 'не прошло'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
