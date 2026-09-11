/**
 * Библиотека собранных кейсов: что есть и что из этого можно забрать.
 *
 * Скачивание живёт здесь, а не в таблице: таблица показывает строки, а запрос
 * с токеном и сохранение файла — работа экрана.
 */
import { Alert, Stack, Text } from '@mantine/core';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { downloadCase, fetchCases } from '../../api/cases';
import type { CaseRow } from '../../api/types';

import { CasesTable } from './CasesTable';
import { failureText } from './failure';
import { saveFile } from './save';

export function CaseLibrary() {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cases = useQuery({ queryKey: ['cases', 'library'], queryFn: () => fetchCases() });

  const take = useMutation({
    mutationFn: (row: CaseRow) => downloadCase(row.id, row.filename ?? `кейс-${row.id}.pdf`),
    onMutate: (row: CaseRow) => {
      setError(null);
      setBusyId(row.id);
    },
    onSuccess: saveFile,
    onError: (failure: unknown) => setError(failureText(failure, 'кейс не скачался')),
    onSettled: () => setBusyId(null),
  });

  return (
    <Stack gap="md">
      {cases.isPending && <Text size="sm">Загружаем библиотеку…</Text>}

      {cases.isError && (
        <Alert color="red" variant="light">
          <Text size="sm">{failureText(cases.error, 'библиотека не загрузилась')}</Text>
        </Alert>
      )}

      {cases.data && cases.data.length === 0 && (
        <Alert color="yellow" variant="light">
          <Text size="sm">
            Кейсов ещё нет. Они собираются по классифицированным проектам — «Пересобрать кейсы»
            соберёт их по текущим вердиктам.
          </Text>
        </Alert>
      )}

      {cases.data && cases.data.length > 0 && (
        <CasesTable rows={cases.data} busyId={busyId} onDownload={(row) => take.mutate(row)} />
      )}

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}
    </Stack>
  );
}
