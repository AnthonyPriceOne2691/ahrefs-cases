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
import { groupWord } from '../groups';

/**
 * Группа, к которой относится условие.
 *
 * Ключ правила выглядит как `good.kw_top10_pct`, и до 15.09.2026 он печатался
 * под каждой строкой целиком. Владелец попросил его убрать — но просто убрать
 * нельзя: **половина условий повторяется дважды**, у «хорошего» и у «среднего»,
 * с одной и той же формулировкой и разными порогами. Без различителя две
 * строки «рост органического трафика в процентах» с порогами 100 и 20 читались
 * бы как ошибка сервиса.
 *
 * Поэтому от ключа остаётся то единственное, что человеку нужно, — группа,
 * названная словом, а не префиксом.
 */
function groupOf(subject: string): string {
  const [prefix] = subject.split('.');
  return prefix && prefix !== subject ? groupWord(prefix) : '';
}

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
          {/* Условие — имя строки, его читают сверху вниз, и рваный левый край
              мешал бы искать глазами. Остальные колонки короткие и одной
              природы, поэтому по центру — то же правило, что в таблице
              кейсов. */}
          <Table.Tr>
            <Table.Th>Условие</Table.Th>
            <Table.Th ta="center">Группа</Table.Th>
            <Table.Th ta="center">Факт</Table.Th>
            <Table.Th ta="center">Порог</Table.Th>
            <Table.Th ta="center">Итог</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={`${row.subject}-${row.note}`} data-subject={row.subject}>
              <Table.Td>
                <Group gap="xs">
                  <Text size="sm">{row.note || row.subject}</Text>
                  {row.decisive && (
                    <Badge size="xs" variant="light" data-decisive="true">
                      решающее
                    </Badge>
                  )}
                </Group>
              </Table.Td>
              <Table.Td ta="center" data-group={groupOf(row.subject)}>
                <Text size="sm" c="dimmed">
                  {groupOf(row.subject) || '—'}
                </Text>
              </Table.Td>
              <Table.Td ta="center">{row.fact === null ? '—' : num(row.fact)}</Table.Td>
              <Table.Td ta="center">{row.threshold === null ? '—' : num(row.threshold)}</Table.Td>
              <Table.Td ta="center" data-passed={row.passed}>
                {row.passed ? 'прошло' : 'не прошло'}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
