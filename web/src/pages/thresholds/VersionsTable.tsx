/**
 * Версии порогов. Действующая помечена: по ней сейчас считаются вердикты.
 *
 * Версия неизменяема — правка это новая версия, потому что вердикты ссылаются
 * на версию, и правка задним числом сделала бы прошлые решения необъяснимыми.
 */
import { Badge, Table, Text } from '@mantine/core';

import type { RulesetRow } from '../../api/types';

function moment(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

interface Props {
  rows: RulesetRow[];
  /** Раскрытая версия. Под её строкой стоит подробность. */
  selected: string | null;
  onSelect: (row: RulesetRow) => void;
}

export function VersionsTable({ rows, selected, onSelect }: Props) {
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Версия</Table.Th>
            <Table.Th>Утверждена</Table.Th>
            <Table.Th>Заметка</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr
              key={row.id}
              data-version={row.version}
              data-selected={row.version === selected ? 'yes' : 'no'}
              onClick={() => onSelect(row)}
              style={{ cursor: 'pointer' }}
            >
              <Table.Td>
                <Text size="sm">{row.version}</Text>
                {row.is_active && (
                  <Badge variant="light" color="teal" data-active="yes">
                    действующая
                  </Badge>
                )}
              </Table.Td>
              <Table.Td>{moment(row.created_at)}</Table.Td>
              <Table.Td>
                <Text size="xs" c="dimmed">
                  {row.note || '—'}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
