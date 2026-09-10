import { Badge, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { fetchHealth } from './api';

/**
 * Каркас Ф1: одна страница, показывающая, что связка фронт → API → база жива.
 * Экраны (загрузка, проекты, карточка, пороги, расход) приходят в Ф6.
 */
export function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 15_000 });

  return (
    <Container size="sm" py="xl">
      <Stack gap="lg">
        <Title order={1}>Ahrefs Cases</Title>
        <Text c="dimmed">Каркас. Сбор, классификация и кейсы приходят фазами Ф2–Ф4.</Text>

        <Paper className="glass" p="lg">
          <Stack gap="sm">
            <Group justify="space-between">
              <Text fw={600}>Состояние сервиса</Text>
              {health.isLoading ? (
                <Badge variant="light">проверяю…</Badge>
              ) : health.data?.status === 'ok' ? (
                <Badge color="teal" variant="light">
                  база на связи
                </Badge>
              ) : (
                <Badge color="red" variant="light">
                  база недоступна
                </Badge>
              )}
            </Group>

            {health.data && (
              <Stack gap={4}>
                <Text size="sm" c="dimmed">
                  провайдер Ahrefs: <b>{health.data.provider}</b>
                  {health.data.provider === 'fixture' &&
                    ' — записанные ответы, квота заказчика не расходуется'}
                </Text>
                {health.data.migration && (
                  <Text size="sm" c="dimmed">
                    схема базы: <b>{health.data.migration}</b>
                  </Text>
                )}
                {health.data.reason && (
                  <Text size="sm" c="red">
                    причина: {health.data.reason}
                  </Text>
                )}
              </Stack>
            )}
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
