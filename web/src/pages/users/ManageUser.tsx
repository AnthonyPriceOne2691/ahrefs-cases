/**
 * Правка выбранного человека: группа, вход, личные права.
 *
 * Право показывается **итогом**: «да» или «нет» — то, что человеку сейчас
 * можно. Третьей кнопки «как в группе» на экране нет: она называла не право, а
 * способ его хранения, и требовала от руководителя держать в голове разницу
 * между «не выдавали» и «отобрали».
 *
 * Хранение при этом осталось трёхзначным, и это не хитрость, а смысл: личное
 * решение, совпавшее с группой, **не записывается**. Значит право продолжает
 * ехать за группой — переведи человека в инженеры, и «править пороги» станет
 * «да» само. Записывается только отличие от группы; оно и переживает перевод.
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

import { DeleteUser } from './DeleteUser';
import { PasswordOnce } from './PasswordOnce';
import { byLabel, rightLabel } from './rights';

const GROUPS = [
  { value: 'user', label: 'пользователь' },
  { value: 'admin', label: 'админ' },
  { value: 'engineer', label: 'инженер' },
];

const STATES = [
  { value: 'yes', label: 'Да' },
  { value: 'no', label: 'Нет' },
];

/** Что человеку сейчас можно: личное решение, а если его нет — то, что даёт
 *  группа. Экран показывает итог, потому что решение принимают про итог. */
function stateOf(
  personal: Record<string, boolean>,
  fromGroup: readonly string[],
  right: string,
): string {
  const allowed = right in personal ? personal[right] : fromGroup.includes(right);
  return allowed ? 'yes' : 'no';
}

function nextPersonal(
  personal: Record<string, boolean>,
  fromGroup: readonly string[],
  right: string,
  state: string,
): Record<string, boolean> {
  // Совпало с группой — личного решения нет вовсе: ключ не попадает в копию, и
  // право продолжает ехать за группой. Записать здесь `true` значило бы
  // приколотить право к человеку намертво, и перевод в другую группу его бы не
  // тронул — а руководитель нажимал «да», а не «навсегда».
  const next = Object.fromEntries(Object.entries(personal).filter(([key]) => key !== right));
  const allowed = state === 'yes';
  if (allowed !== fromGroup.includes(right)) next[right] = allowed;
  return next;
}

/** Право и ответ рядом, а не по краям панели: глазу не надо ехать через всю
 *  ширину, чтобы связать «править пороги» с «да». */
function RightRow({
  right,
  value,
  onChange,
}: {
  right: string;
  value: string;
  onChange: (state: string) => void;
}) {
  return (
    <Group gap="sm" wrap="nowrap">
      <Text size="sm" w={200}>
        {rightLabel(right)}
      </Text>
      <SegmentedControl
        w="fit-content"
        size="xs"
        data={STATES}
        value={value}
        aria-label={rightLabel(right)}
        onChange={onChange}
      />
    </Group>
  );
}

interface Props {
  user: UserRow;
  catalog: RightsCatalog;
  onChanged: () => void;
  /** Человека удалили: панель закрывается — показывать нечего. */
  onDeleted: () => void;
}

export function ManageUser({ user, catalog, onChanged, onDeleted }: Props) {
  // Набор группы — то, от чего считается «да» по умолчанию. Берётся из
  // справочника сервера, а не из второй таблицы прав на фронте (урок L101).
  const fromGroup = catalog.groups[user.group] ?? [];
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
        {/* Ширина по содержимому: растянутый на всю панель переключатель из
            двух слов обещает выбор, которого в нём нет. */}
        <SegmentedControl
          w="fit-content"
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

      <Text size="sm">Что человеку можно</Text>
      {byLabel(catalog.rights).map((right) => (
        <RightRow
          key={right}
          right={right}
          value={stateOf(user.personal_rights, fromGroup, right)}
          onChange={(state) =>
            change.mutate({
              personal_rights: nextPersonal(user.personal_rights, fromGroup, right, state),
            })
          }
        />
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

      <DeleteUser user={user} onDeleted={onDeleted} />

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
