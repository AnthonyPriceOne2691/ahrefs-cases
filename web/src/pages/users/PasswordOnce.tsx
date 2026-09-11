/**
 * Пароль, показанный один раз.
 *
 * В базе только хеш — повторить показ сервер не сможет при всём желании, и
 * человек должен это понимать **в момент показа**, а не когда закроет панель.
 * Отсюда прямая формулировка и кнопка «Записал», которая убирает пароль с
 * экрана осознанно, а не по таймеру.
 */
import { Alert, Button, Code, Group, Stack, Text } from '@mantine/core';

interface Props {
  email: string;
  password: string;
  onHide: () => void;
}

export function PasswordOnce({ email, password, onHide }: Props) {
  return (
    <Alert color="blue" variant="light">
      <Stack gap="xs">
        <Text size="sm" fw={600}>
          Пароль для {email} — он показывается один раз
        </Text>
        <Code data-password>{password}</Code>
        <Text size="xs">
          Второго показа не будет: сервис хранит только хеш. Потеряется — выпустите новый, старый
          перестанет работать сразу.
        </Text>
        <Group>
          <Button size="compact-sm" variant="light" onClick={onHide}>
            Записал, убрать с экрана
          </Button>
        </Group>
      </Stack>
    </Alert>
  );
}
