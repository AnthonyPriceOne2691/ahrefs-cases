/**
 * Заведение человека.
 *
 * Пароль придумывает сервер, а не руководитель: придуманный руками попадает в
 * переписку и живёт там дольше учётки. Здесь он только показывается — один раз.
 */
import {
  Alert,
  Button,
  Group,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { createUser } from '../../api/users';
import type { UserWithPassword } from '../../api/types';
import { failureText } from '../cases/failure';

import { PasswordOnce } from './PasswordOnce';

const GROUPS = [
  { value: 'user', label: 'пользователь' },
  { value: 'admin', label: 'админ' },
  { value: 'engineer', label: 'инженер' },
];

export function CreateUser({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [group, setGroup] = useState('user');
  const [made, setMade] = useState<UserWithPassword | null>(null);
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => createUser(email.trim(), fullName.trim(), group),
    onMutate: () => setError(null),
    onSuccess: (created) => {
      setMade(created);
      setEmail('');
      setFullName('');
      onCreated();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'человек не заведён')),
  });

  return (
    <Stack gap="sm">
      <Title order={4}>Завести человека</Title>
      <Group grow align="flex-end">
        <TextInput
          label="Почта (она же логин)"
          placeholder="name@agency.local"
          value={email}
          onChange={(event) => setEmail(event.currentTarget.value)}
        />
        <TextInput
          label="Имя"
          value={fullName}
          onChange={(event) => setFullName(event.currentTarget.value)}
        />
      </Group>

      <Stack gap={4}>
        <Text size="sm">Группа</Text>
        {/* Не `Select`: попап Mantine в jsdom рендерится секундами, и тест
            файла уходил в таймаут (урок L76). Здесь выбор из трёх — переключатель
            читается не хуже и стоит дешевле. */}
        <SegmentedControl data={GROUPS} value={group} onChange={setGroup} />
      </Stack>

      <Group>
        <Button loading={add.isPending} disabled={email.trim() === ''} onClick={() => add.mutate()}>
          Завести и показать пароль
        </Button>
      </Group>

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}

      {made && (
        <PasswordOnce
          email={made.user.email}
          password={made.password}
          onHide={() => setMade(null)}
        />
      )}
    </Stack>
  );
}
