/**
 * Список людей и его состояния.
 *
 * Отдельно от страницы, потому что состояний четыре — грузится, есть строки,
 * пусто, отказ — и вместе с заголовком и обвязкой они складываются в один
 * компонент, который гейт длины ловит справедливо (урок L91).
 */
import { Alert, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { fetchRights, fetchUsers } from '../../api/users';
import { failureText } from '../cases/failure';

import { UsersTable } from './UsersTable';

/** Людей нет — это не пустая таблица, а сервис, в который некому войти. */
function Empty() {
  return (
    <Alert color="yellow" variant="light">
      <Text size="sm">
        Людей нет. Первый администратор заводится командой «useradd» при установке — если список
        пуст, войти в сервис не может никто.
      </Text>
    </Alert>
  );
}

export function UsersBody() {
  const users = useQuery({ queryKey: ['users'], queryFn: () => fetchUsers() });
  const catalog = useQuery({ queryKey: ['users', 'rights'], queryFn: fetchRights });

  const failure = users.error ?? catalog.error;
  if (failure) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">{failureText(failure, 'список людей не загрузился')}</Text>
      </Alert>
    );
  }

  // `isPending` тайпгардом не является: проверяем сами данные — иначе ветка
  // «загрузка» и ветка «данные есть» расходятся с типами.
  const rows = users.data;
  const rights = catalog.data;
  if (!rows || !rights) return <Text size="sm">Загружаем людей…</Text>;
  if (rows.length === 0) return <Empty />;

  return (
    <Stack gap="md">
      <UsersTable rows={rows} catalog={rights} />
    </Stack>
  );
}
