/**
 * Экран загрузки: дать список, увидеть цену, запустить прогон.
 *
 * Первый экран основного сценария целиком. Остальные показывают результат, а
 * этот начинает работу и тратит деньги — поэтому смета и запрет запуска живут
 * рядом с кнопкой, а не в отдельном разделе.
 */
import { Alert, Container, Paper, Stack, Text, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../api/client';
import { fetchEstimate, fetchRun, startRun, uploadLink, uploadList } from '../api/intake';
import type { IntakeReport } from '../api/types';

import { EstimatePanel } from './intake/EstimatePanel';
import { IntakeOutcome } from './intake/IntakeOutcome';
import { RUNNING } from './intake/RunLine';
import { SourceForm } from './intake/SourceForm';

const ESTIMATE_KEY = ['runs', 'estimate'];
const POLL_MS = 5_000;

/** Текст отказа берём у сервера: он называет формат, доступ или номер активного
 *  прогона. «Что-то пошло не так» оставило бы человека без следующего шага. */
function failureText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function IntakePage() {
  const queryClient = useQueryClient();
  const [report, setReport] = useState<IntakeReport | null>(null);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  const estimate = useQuery({ queryKey: ESTIMATE_KEY, queryFn: fetchEstimate });

  const run = useQuery({
    queryKey: ['runs', runId],
    queryFn: () => fetchRun(runId as number),
    enabled: runId !== null,
    // Пока прогон идёт, экран обновляет его сам: нажавший кнопку человек не
    // должен перезагружать страницу, чтобы узнать, началось ли.
    refetchInterval: (query) => (RUNNING.has(query.state.data?.status ?? '') ? POLL_MS : false),
  });

  const accept = useMutation({
    mutationFn: (source: File | string) =>
      typeof source === 'string' ? uploadLink(source) : uploadList(source),
    onMutate: () => {
      setIntakeError(null);
      setReport(null);
    },
    onSuccess: async (accepted) => {
      setReport(accepted);
      // Список изменился — значит изменилась и цена. Без этого смета осталась бы
      // ценой предыдущего списка, и решение о запуске принималось бы по ней.
      await queryClient.invalidateQueries({ queryKey: ESTIMATE_KEY });
    },
    onError: (error: unknown) => setIntakeError(failureText(error, 'список не принят')),
  });

  const launch = useMutation({
    mutationFn: startRun,
    onMutate: () => setStartError(null),
    onSuccess: async (started) => {
      setRunId(started.run_id);
      await queryClient.invalidateQueries({ queryKey: ESTIMATE_KEY });
    },
    onError: (error: unknown) => setStartError(failureText(error, 'прогон не начат')),
  });

  return (
    <Container size="lg">
      <Stack gap="lg">
        <Title order={2}>Загрузка</Title>

        <Paper className="glass" p="lg">
          <SourceForm
            busy={accept.isPending}
            error={intakeError}
            onSubmit={(source) => accept.mutate(source)}
          />
        </Paper>

        {report && (
          <Paper className="glass" p="lg">
            <IntakeOutcome report={report} />
          </Paper>
        )}

        <Paper className="glass" p="lg">
          {estimate.isPending && <Text size="sm">Считаем смету…</Text>}
          {estimate.isError && (
            <Alert color="red" variant="light">
              <Text size="sm">{failureText(estimate.error, 'смета не посчитана')}</Text>
            </Alert>
          )}
          {estimate.data && (
            <EstimatePanel
              estimate={estimate.data}
              run={run.data ?? null}
              starting={launch.isPending}
              startError={startError}
              onStart={() => launch.mutate()}
            />
          )}
        </Paper>
      </Stack>
    </Container>
  );
}
