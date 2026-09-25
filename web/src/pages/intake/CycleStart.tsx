/**
 * Цикл по загруженному списку: смета всего цикла и одна кнопка «Запустить».
 *
 * Решение владельца 25.09.2026: «прикрепил ссылку или файл — логика
 * проанализировала — предварительная смета — стартует прогон — скачать
 * кейсы». Прогон идёт по проектам этого списка, а не по всей базе, и в
 * журнале это одна строка: шаг 1, шаг 2, данные под кейс и сборка — внутри
 * неё. Смета — по верхней границе; не хватает units — кнопка недоступна, а
 * сервер откажет и сам.
 */
import { Alert, Text } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { fetchCycleEstimate, startCycle } from '../../api/intake';
import { failureText } from '../cases/failure';

import { EstimatePanel } from './EstimatePanel';
import type { EstimateWords } from './EstimatePanel';

const CYCLE_WORDS: EstimateWords = {
  title: 'Весь цикл по этому списку',
  count: 'проектов',
  start: 'Запустить',
  empty: 'В списке нет принятых проектов — запускать нечего.',
};

interface Props {
  projectIds: number[];
  onStarted: (runId: number) => void;
}

export function CycleStart({ projectIds, onStarted }: Props) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState<number | null>(null);

  const estimate = useQuery({
    queryKey: ['runs', 'cycle', 'estimate', projectIds],
    queryFn: () => fetchCycleEstimate(projectIds),
    enabled: projectIds.length > 0,
  });

  const launch = useMutation({
    mutationFn: () => startCycle(projectIds),
    onMutate: () => setError(null),
    onSuccess: async (run) => {
      setStarted(run.run_id);
      onStarted(run.run_id);
      await queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
    onError: (failure: unknown) =>
      setError(failure instanceof ApiError ? failure.message : 'цикл не начат'),
  });

  if (projectIds.length === 0) return null;
  if (started !== null) {
    return (
      <Alert color="teal" variant="light" data-cycle-started={started}>
        <Text size="sm">
          Цикл запущен: прогон №{started} в журнале ниже. «Скачать» в его строке станет активной,
          когда соберутся кейсы.
        </Text>
      </Alert>
    );
  }
  if (estimate.isPending) return <Text size="sm">Считаем смету цикла…</Text>;
  if (estimate.isError || !estimate.data) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">{failureText(estimate.error, 'смета цикла не посчиталась')}</Text>
      </Alert>
    );
  }
  return (
    <EstimatePanel
      estimate={estimate.data}
      run={null}
      starting={launch.isPending}
      startError={error}
      onStart={() => launch.mutate()}
      words={CYCLE_WORDS}
    />
  );
}
