/**
 * Правка выбранного человека: группа, вход, личные права.
 *
 * Личное право — **три состояния**, а не галочка: «как в группе», «выдать»,
 * «отобрать». Третье существует ровно потому, что группа право даёт, а этому
 * человеку оно не нужно, — и галочкой это не выражается: снятая галочка
 * неотличима от «не выдавали».
 *
 * Отказы сервера показываются его словами: последний администратор, выключение
 * себя и неизвестное право — разные запреты с разными причинами.
 */
import { Alert, Button, Group, SegmentedControl, Stack, Switch, Text, Title } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import type { RightsCatalog, UserRow, UserWithPassword } from '../../api/types';
import { patchUser, resetPassword } from '../../api/users';
import { failureText } from '../cases/failure';

import { PasswordOnce } from './PasswordOnce';
import { byLabel, rightLabel } from './rights';

const GROUPS = [
  { value: 'user', label: 'пользователь' },
  { value: 'admin', label: 'админ' },
  { value: 'engineer', label: 'инженер' },
];

const STATES = [
  { value: 'group', label: 'как в группе' },
  { value: 'grant', label: 'выдать' },
  { value: 'revoke', label: 'отобрать' },
];

/** Личное решение о праве → значение переключателя. Отсутствие ключа и есть
 *  «как в группе»: это не то же, что выданное или отобранное. */
function stateOf(personal: Record<string, boolean>, right: string): string {
  if (!(right in personal)) return 'group';
  return personal[right] ? 'grant' : 'revoke';
}

function nextPersonal(
  personal: Record<string, boolean>,
  right: string,
  state: string,
): Record<string, boolean> {
  // «Как в группе» — это **отсутствие** ключа, а не `false`: `false` означает
  // «отобрано» и переживёт смену группы. Поэтому ключ не удаляется из копии,
  // а не попадает в неё вовсе.
  const next = Object.fromEntries(Object.entries(personal).filter(([key]) => key !== right));
  if (state !== 'group') next[right] = state === 'grant';
  return next;
}

interface Props {
  user: UserRow;
  catalog: RightsCatalog;
  onChanged: () => void;
}

export function ManageUser({ user, catalog, onChanged }: Props) {
  const [password, setPassword] = useState<UserWithPassword | null>(null);
  const [error, setError] = useState<string | null>(null);

  const change = useMutation({
    mutationFn: (patch: Parameters<typeof patchUser>[1]) => patchUser(user.id, patch),
    onMutate: () => setError(null),
    onSuccess: onChanged,
    onError: (failure: unknown) => setError(failureText(failure, 'изменение не принято')),
  });

  const renew = useMutation({
    mutationFn: () => resetPassword(user.id),
    onMutate: () => setError(null),
    onSuccess: setPassword,
    onError: (failure: unknown) => setError(failureText(failure, 'пароль не перевыпущен')),
  });

  return (
    <Stack gap="sm">
      <Title order={4}>{user.email}</Title>

      <Stack gap={4}>
        <Text size="sm">Группа</Text>
        <SegmentedControl
          data={GROUPS}
          value={user.group}
          onChange={(group) => change.mutate({ group })}
        />
      </Stack>

      <Switch
        label="вход разрешён"
        checked={user.is_active}
        onChange={(event) => change.mutate({ is_active: event.currentTarget.checked })}
      />

      <Text size="sm">Личные права — поверх группы</Text>
      {byLabel(catalog.rights).map((right) => (
        <Group key={right} justify="space-between" wrap="nowrap">
          <Text size="sm">{rightLabel(right)}</Text>
          <SegmentedControl
            size="xs"
            data={STATES}
            value={stateOf(user.personal_rights, right)}
            aria-label={rightLabel(right)}
            onChange={(state) =>
              change.mutate({
                personal_rights: nextPersonal(user.personal_rights, right, state),
              })
            }
          />
        </Group>
      ))}

      <Group>
        <Button
          size="compact-sm"
          variant="light"
          loading={renew.isPending}
          onClick={() => renew.mutate()}
        >
          Выпустить новый пароль
        </Button>
      </Group>

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}

      {password && (
        <PasswordOnce
          email={password.user.email}
          password={password.password}
          onHide={() => setPassword(null)}
        />
      )}
    </Stack>
  );
}
