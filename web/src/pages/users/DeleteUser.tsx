/**
 * Удаление пользователя — с подтверждением на месте.
 *
 * Подтверждение обязательно: удаление необратимо, а кнопка стоит рядом с
 * переключателями прав, по которым кликают часто. Спрашиваем прямо здесь, а не
 * попапом: попапы Mantine в jsdom рендерятся секундами, и проверить такой шаг
 * дорого (урок L76).
 *
 * Текст подтверждения называет **последствие, а не действие**: человек решает
 * не «нажать ли кнопку», а что будет с журналом прогонов.
 */
import { Alert, Button, Group, Text } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { deleteUser } from '../../api/users';
import { ConfirmDelete } from '../../components/ConfirmDelete';
import type { UserRow } from '../../api/types';
import { failureText } from '../cases/failure';

interface Props {
  user: UserRow;
  onDeleted: () => void;
}

export function DeleteUser({ user, onDeleted }: Props) {
  const [asked, setAsked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const drop = useMutation({
    mutationFn: () => deleteUser(user.id),
    onMutate: () => setError(null),
    onSuccess: () => {
      setAsked(false);
      onDeleted();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'пользователь не удалён')),
  });

  return (
    <>
      {!asked && (
        <Group>
          <Button size="compact-sm" variant="light" color="red" onClick={() => setAsked(true)}>
            Удалить пользователя
          </Button>
        </Group>
      )}

      {asked && (
        <Alert color="red" variant="light">
          <Text size="sm">
            Удалить {user.email}? Войти он больше не сможет, а прогоны, которые он запускал,
            останутся в журнале — там он будет помечен как удалённый.
          </Text>
          <ConfirmDelete
            busy={drop.isPending}
            onConfirm={() => drop.mutate()}
            onCancel={() => setAsked(false)}
          />
        </Alert>
      )}

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}
    </>
  );
}
