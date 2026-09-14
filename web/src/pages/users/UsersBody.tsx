/**
 * Список людей и его состояния.
 *
 * Отдельно от страницы, потому что состояний четыре — грузится, есть строки,
 * пусто, отказ — и вместе с заголовком и обвязкой они складываются в один
 * компонент, который гейт длины ловит справедливо (урок L91).
 */
import { Alert, Collapse, Divider, Stack, Text } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import { fetchRights, fetchUsers } from '../../api/users';
import { failureText } from '../cases/failure';

import { CreateUser } from './CreateUser';
import { ManageUser } from './ManageUser';
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

const FOLD_MS = 220;
/** Длительность сворачивания. Столько же ждёт открытие следующего человека:
 *  две панели, едущие навстречу друг другу, читаются как рывок. */

export function UsersBody() {
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState<number | null>(null);
  // Панель остаётся на экране, пока едет вниз: убери её сразу — и сворачивать
  // будет нечего, вместо анимации получится мгновенное исчезновение.
  const [shown, setShown] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Нажатие на человека. Три случая, и они разные:
   *
   * - тот же самый — свернуть (нажатие повторяет вопрос, ответ — закрыть);
   * - никого не открыто — открыть сразу;
   * - открыт другой — сначала свернуть его, потом открыть нового, иначе
   *   содержимое подменяется под открытой панелью и выглядит как подмена.
   */
  function choose(id: number) {
    if (timer.current) clearTimeout(timer.current);
    if (chosen === id) {
      setChosen(null);
      return;
    }
    if (chosen === null) {
      setShown(id);
      setChosen(id);
      return;
    }
    setChosen(null);
    timer.current = setTimeout(() => {
      setShown(id);
      setChosen(id);
    }, FOLD_MS);
  }
  const users = useQuery({ queryKey: ['users'], queryFn: () => fetchUsers() });
  const catalog = useQuery({ queryKey: ['users', 'rights'], queryFn: fetchRights });

  // Список — и есть подтверждение, что сервер согласился: после каждой правки
  // он перезапрашивается, и в строке видно, что получилось на самом деле.
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['users'] });

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
  if (rows.length === 0) {
    // Людей нет — но форма заведения нужна именно здесь: иначе единственный
    // ответ экрана «никого нет» не ведёт никуда.
    return (
      <Stack gap="md">
        <Empty />
        <CreateUser onCreated={refresh} />
      </Stack>
    );
  }

  const selected = rows.find((row) => row.id === shown) ?? null;

  return (
    <Stack gap="md">
      <UsersTable
        rows={rows}
        catalog={rights}
        selected={chosen}
        onSelect={(user) => choose(user.id)}
      />

      {selected && (
        <Collapse in={chosen === selected.id} transitionDuration={FOLD_MS}>
          <Stack gap="md">
            <Divider />
            <ManageUser
              user={selected}
              catalog={rights}
              onChanged={refresh}
              onDeleted={() => {
                setChosen(null);
                refresh();
              }}
            />
          </Stack>
        </Collapse>
      )}

      <Divider />
      <CreateUser onCreated={refresh} />
    </Stack>
  );
}
