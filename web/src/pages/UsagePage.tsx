/**
 * Расход units — единственного платного ресурса сервиса.
 *
 * Экран отвечает за загрузку, отказ и поводы; сами числа и то, что из них
 * следует, живут в `usage/UsageTotals.tsx` — там же объяснено, почему их
 * четыре. Остаток, которого не узнали, — слово, а не ноль: ноль означал бы
 * «квота кончилась» и читался бы как запрет.
 */
import { Alert, Container, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '../api/client';
import { fetchAlerts, fetchUsage } from '../api/ops';

import { Alerts } from './usage/Alerts';
import { UsageTotals } from './usage/UsageTotals';

export function UsagePage() {
  const usage = useQuery({ queryKey: ['usage'], queryFn: fetchUsage });
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: fetchAlerts });

  return (
    <Container size="lg">
      <Stack gap="lg">
        <Title order={2}>Расход units</Title>

        <Paper className="glass" p="lg">
          <Stack gap="md">
            {usage.isPending && <Text size="sm">Считаем расход…</Text>}

            {usage.isError && (
              <Alert color="red" variant="light">
                <Text size="sm">
                  {usage.error instanceof ApiError ? usage.error.message : 'расход не загрузился'}
                </Text>
              </Alert>
            )}

            {usage.data && <UsageTotals usage={usage.data} />}
          </Stack>
        </Paper>

        <Paper className="glass" p="lg">
          <Stack gap="sm">
            <Title order={3}>Поводы</Title>
            {alerts.isPending && <Text size="sm">Проверяем…</Text>}
            {alerts.data && <Alerts rows={alerts.data} />}
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
