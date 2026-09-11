/**
 * Состояние пачки и действия над ней: скачать, пересобрать.
 *
 * Отдельно от библиотеки, потому что это разные работы: библиотека отвечает
 * «что собрано», пачка — «что можно забрать целиком». Сведённые в один
 * компонент, они и в коде выглядели как одна (гейт поймал это длиной функции).
 */
import { Alert, Text } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { downloadPack, fetchPack, startCasesRun } from '../../api/cases';
import { useAuth } from '../../auth/AuthProvider';

import { PackCard } from './PackCard';
import { failureText } from './failure';
import { saveFile } from './save';

const PACK_KEY = ['cases', 'pack'];

export function PackSection() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [startedRunId, setStartedRunId] = useState<number | null>(null);

  const pack = useQuery({ queryKey: PACK_KEY, queryFn: fetchPack });

  const take = useMutation({
    mutationFn: () => downloadPack(pack.data?.filename ?? 'кейсы.zip'),
    onMutate: () => setError(null),
    onSuccess: saveFile,
    onError: (failure: unknown) => setError(failureText(failure, 'пачка не скачалась')),
  });

  const rebuild = useMutation({
    mutationFn: startCasesRun,
    onMutate: () => setError(null),
    onSuccess: async (started) => {
      setStartedRunId(started.run_id);
      // Прогон идёт в фоне и закончится позже: состояние пачки перезапрашиваем,
      // чтобы вернувшийся на экран человек увидел свежий архив, а не прежний.
      await queryClient.invalidateQueries({ queryKey: PACK_KEY });
    },
    onError: (failure: unknown) => setError(failureText(failure, 'сборка не начата')),
  });

  if (pack.isPending) return <Text size="sm">Смотрим, что собрано…</Text>;
  if (pack.isError || !pack.data) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">{failureText(pack.error, 'состояние пачки не загрузилось')}</Text>
      </Alert>
    );
  }

  return (
    <PackCard
      pack={pack.data}
      canRun={can('run')}
      downloading={take.isPending}
      rebuilding={rebuild.isPending}
      startedRunId={startedRunId}
      error={error}
      onDownload={() => take.mutate()}
      onRebuild={() => rebuild.mutate()}
    />
  );
}
