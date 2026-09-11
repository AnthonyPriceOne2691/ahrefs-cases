/**
 * Журнал прогонов.
 *
 * Экран обновляется сам, **пока есть незакрытый прогон**, и перестаёт, когда
 * все закончились: прогон идёт часами, а экран открыт минутами — постоянный
 * опрос греет базу ради секунды точности.
 */
import { Alert, Container, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '../api/client';
import { fetchRuns } from '../api/ops';
import type { RunRow } from '../api/types';

import { RunsTable } from './runs/RunsTable';

const POLL_MS = 5_000;
const OPEN = new Set(['queued', 'running']);

/** Активный прогон ищется по **всем** строкам, а не по первой: номер растёт, а
 *  закончиться прогон может раньше соседа. */
function hasOpenRun(rows: RunRow[] | undefined): boolean {
  return (rows ?? []).some((run) => OPEN.has(run.status));
}

export function RunsPage() {
  const runs = useQuery({
    queryKey: ['runs', 'journal'],
    queryFn: () => fetchRuns(),
    refetchInterval: (query) => (hasOpenRun(query.state.data) ? POLL_MS : false),
  });

  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Прогоны</Title>
        <Paper className="glass" p="lg">
          <Stack gap="md">
            {runs.isPending && <Text size="sm">Загружаем журнал…</Text>}

            {runs.isError && (
              <Alert color="red" variant="light">
                <Text size="sm">
                  {runs.error instanceof ApiError ? runs.error.message : 'журнал не загрузился'}
                </Text>
              </Alert>
            )}

            {runs.data && runs.data.length === 0 && (
              <Alert color="yellow" variant="light">
                <Text size="sm">
                  Прогонов ещё не было. Запустить можно на экране «Загрузка» — там же видно смету.
                </Text>
              </Alert>
            )}

            {runs.data && runs.data.length > 0 && <RunsTable rows={runs.data} />}

            {hasOpenRun(runs.data) && (
              <Text size="xs" c="dimmed">
                Прогон идёт: журнал обновляется сам.
              </Text>
            )}
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
