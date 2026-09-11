/**
 * Версии порогов. Действующая помечена: по ней сейчас считаются вердикты.
 *
 * Версия неизменяема — правка это новая версия, потому что вердикты ссылаются
 * на версию, и правка задним числом сделала бы прошлые решения необъяснимыми.
 */
import { Badge, Button, Table, Text } from '@mantine/core';

import type { RulesetRow } from '../../api/types';

function moment(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

interface Props {
  rows: RulesetRow[];
  selected: string | null;
  /** Версия, по которой сейчас считается предпросмотр. */
  busyVersion: string | null;
  onSelect: (row: RulesetRow) => void;
  onPreview: (row: RulesetRow) => void;
}

export function VersionsTable({ rows, selected, busyVersion, onSelect, onPreview }: Props) {
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Версия</Table.Th>
            <Table.Th>Утверждена</Table.Th>
            <Table.Th>Заметка</Table.Th>
            <Table.Th>Последствия</Table.Th>
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
              <Table.Td>
                <Button
                  size="compact-sm"
                  variant="light"
                  loading={busyVersion === row.version}
                  onClick={(event) => {
                    // Клик по строке выбирает версию, клик по кнопке — считает:
                    // без остановки всплытия одно нажатие делало бы оба.
                    event.stopPropagation();
                    onPreview(row);
                  }}
                >
                  Что изменится
                </Button>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
