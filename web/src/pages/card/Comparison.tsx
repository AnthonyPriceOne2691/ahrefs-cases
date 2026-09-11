/**
 * Таблица «точка А → точка Б» — та же, что в кейсе.
 *
 * Строки приходят с сервера готовыми: подписи метрик и арифметика роста живут
 * в кейсе и классификации, и вторая копия здесь разошлась бы с первой.
 */
import { Table, Text } from '@mantine/core';

import type { ComparisonRow } from '../../api/types';
import { growth, num } from '../format';

export function Comparison({ rows }: { rows: ComparisonRow[] }) {
  if (rows.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Сравнивать нечего: метрики есть только в одной из точек.
      </Text>
    );
  }
  return (
    <Table.ScrollContainer minWidth={520}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Метрика</Table.Th>
            <Table.Th>Точка А</Table.Th>
            <Table.Th>Точка Б</Table.Th>
            <Table.Th>Рост</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={row.subject} data-subject={row.subject}>
              <Table.Td>{row.label}</Table.Td>
              <Table.Td>{num(row.before)}</Table.Td>
              <Table.Td>{num(row.after)}</Table.Td>
              <Table.Td>{growth(row.pct, row.absolute)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
