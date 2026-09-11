/**
 * Кто заведён в сервисе.
 *
 * Выключенная учётка остаётся в списке: человек заведён, войти не может, и это
 * разные вещи. Удаления нет вовсе — за учёткой тянутся прогоны и расход, и
 * стереть её значит потерять, кто их запускал.
 */
import { Badge, Stack, Table, Text } from '@mantine/core';

import type { RightsCatalog, UserRow } from '../../api/types';

import { RightsCell } from './RightsCell';
import { rightStates } from './rights';

const GROUP_LABELS: Record<string, string> = {
  engineer: 'инженер',
  admin: 'админ',
  user: 'пользователь',
};

interface Props {
  rows: UserRow[];
  catalog: RightsCatalog;
  selected: number | null;
  onSelect: (user: UserRow) => void;
}

export function UsersTable({ rows, catalog, selected, onSelect }: Props) {
  return (
    <Table.ScrollContainer minWidth={860}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Почта</Table.Th>
            <Table.Th>Имя</Table.Th>
            {/* Ширина задана: без неё таблица сжимала колонки под текст соседей,
                и Mantine обрезал бейдж многоточием — «ПОЛЬЗО…» вместо группы.
                Найдено прогоном живого экрана. */}
            <Table.Th style={{ minWidth: 150 }}>Группа</Table.Th>
            <Table.Th style={{ minWidth: 170 }}>Вход</Table.Th>
            <Table.Th>Что можно</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((user) => (
            <Table.Tr
              key={user.id}
              data-user={user.id}
              data-selected={user.id === selected ? 'yes' : 'no'}
              onClick={() => onSelect(user)}
              style={{ cursor: 'pointer' }}
            >
              <Table.Td>{user.email}</Table.Td>
              <Table.Td>
                <Text size="sm">{user.full_name || '—'}</Text>
              </Table.Td>
              <Table.Td>
                <Badge variant="light" data-group={user.group} style={{ maxWidth: 'none' }}>
                  {GROUP_LABELS[user.group] ?? user.group}
                </Badge>
              </Table.Td>
              <Table.Td>
                {user.is_active ? (
                  <Text size="xs" c="dimmed">
                    может войти
                  </Text>
                ) : (
                  <Badge
                    variant="light"
                    color="orange"
                    data-active="no"
                    style={{ maxWidth: 'none' }}
                  >
                    вход закрыт
                  </Badge>
                )}
              </Table.Td>
              <Table.Td>
                <Stack gap={4}>
                  <RightsCell
                    states={rightStates(user.personal_rights, catalog.groups[user.group] ?? [])}
                  />
                </Stack>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
