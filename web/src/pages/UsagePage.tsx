/**
 * Расход units — единственного платного ресурса сервиса.
 *
 * Резерв показан отдельным числом: он удерживает units идущего прогона, и без
 * него остаток выглядит больше, чем есть. Остаток, которого не узнали, — слово,
 * а не ноль: ноль означал бы «квота кончилась» и читался бы как запрет.
 */
import { Alert, Badge, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '../api/client';
import { fetchAlerts, fetchUsage } from '../api/ops';

import { num } from './format';
import { Alerts } from './usage/Alerts';

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

            {usage.data && (
              <>
                <Group gap="xs">
                  <Badge size="lg" variant="light" color="grape" data-usage="spent">
                    потрачено {num(usage.data.spent)}
                  </Badge>
                  <Badge size="lg" variant="light" color="gray" data-usage="reserved">
                    удержано резервом {num(usage.data.reserved)}
                  </Badge>
                  <Badge size="lg" variant="light" data-usage="remaining">
                    остаток{' '}
                    {usage.data.remaining === null ? 'неизвестен' : num(usage.data.remaining)}
                  </Badge>
                </Group>
                <Text size="sm">
                  {usage.data.per_hundred_domains === null
                    ? 'Стоимость запуска на сто доменов пока не из чего вывести: прогонов не было.'
                    : `Стоимость запуска на сто доменов по факту: ${num(usage.data.per_hundred_domains)} units.`}
                </Text>
              </>
            )}
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
