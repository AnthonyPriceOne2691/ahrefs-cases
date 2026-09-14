/**
 * Пользователи: кто заведён и что кому можно.
 *
 * Права двухслойны: группа даёт набор, личное решение перекрывает его в обе
 * стороны. Поэтому экран показывает не только «что можно», но и откуда это
 * взялось — иначе «админ, которому отобрали право» выглядит как обычный админ.
 */
import { Container, Paper, Stack, Title } from '@mantine/core';

import { UsersBody } from './users/UsersBody';

export function UsersPage() {
  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Пользователи</Title>
        <Paper className="glass" p="lg">
          <UsersBody />
        </Paper>
      </Stack>
    </Container>
  );
}
