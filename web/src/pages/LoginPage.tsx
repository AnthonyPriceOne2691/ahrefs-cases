/**
 * Вход. Ошибка одна на все причины — так же, как отвечает сервер.
 *
 * Разные сообщения («нет такой почты» против «неверный пароль») превратили бы
 * форму в перечислитель учётных записей агентства.
 */
import {
  Alert,
  Button,
  Container,
  Paper,
  PasswordInput,
  Stack,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthProvider';

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (failure: unknown) {
      setError(
        failure instanceof ApiError && failure.misconfigured
          ? failure.message
          : 'неверная почта или пароль',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container size={420} py="20vh">
      <Paper className="glass" p="xl">
        <form onSubmit={submit}>
          <Stack gap="md">
            <Title order={2}>Вход</Title>
            <TextInput
              label="Почта"
              value={email}
              onChange={(event) => setEmail(event.currentTarget.value)}
              autoComplete="username"
              required
            />
            <PasswordInput
              label="Пароль"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              autoComplete="current-password"
              required
            />
            {error && (
              <Alert color="red" variant="light">
                {error}
              </Alert>
            )}
            <Button type="submit" loading={busy}>
              Войти
            </Button>
          </Stack>
        </form>
      </Paper>
    </Container>
  );
}
