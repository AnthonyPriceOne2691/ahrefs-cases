/**
 * Вторая кнопка экрана прогонов: шаг 2 по кандидатам и данные под кейс (B6).
 *
 * Решение владельца 24.09.2026: прогон из интерфейса делает шаг 1 и бесплатную
 * классификацию, а дорогие ступени воронки тратят units отдельным нажатием со
 * своей сметой. Кандидаты к этому моменту уже известны — смета точная.
 *
 * Кнопка и её окно живут вместе и отдельно от экрана: у окна своё состояние,
 * своя ошибка запуска и свой признак «открыто», переживающий F5 (L182).
 */
import { Button } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { fetchStage2Estimate, startStage2 } from '../../api/intake';
import type { RunRow } from '../../api/types';
import { useStickyFlag } from '../../app/stickyFlag';
import type { EstimateWords } from '../intake/EstimatePanel';

import { EstimateWindow } from './EstimateWindow';

const STAGE2_KEY = ['runs', 'stage2', 'estimate'];

const STAGE2_WORDS: EstimateWords = {
  title: 'Шаг 2 и данные под кейс',
  count: 'кандидатов',
  start: 'Запустить шаг 2',
  empty: 'Кандидатов нет: шаг 1 не нашёл проектов, которым стоит платить за шаг 2.',
};

interface Props {
  run: RunRow | null;
  onStarted: (runId: number) => void;
}

export function Stage2Launcher({ run, onStarted }: Props) {
  const queryClient = useQueryClient();
  const [opened, setOpened] = useStickyFlag('шаг2');
  const [error, setError] = useState<string | null>(null);

  const launch = useMutation({
    mutationFn: startStage2,
    onMutate: () => setError(null),
    onSuccess: async (started) => {
      onStarted(started.run_id);
      await queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
    onError: (failure: unknown) =>
      setError(failure instanceof ApiError ? failure.message : 'шаг 2 не начат'),
  });

  return (
    <>
      <Button variant="light" onClick={() => setOpened(true)}>
        Дособрать кандидатов
      </Button>
      <EstimateWindow
        opened={opened}
        onClose={() => setOpened(false)}
        run={run}
        starting={launch.isPending}
        startError={error}
        onStart={() => launch.mutate()}
        queryKey={STAGE2_KEY}
        fetcher={fetchStage2Estimate}
        words={STAGE2_WORDS}
      />
    </>
  );
}
