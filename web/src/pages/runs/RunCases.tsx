/**
 * Кейсы прямо из строки журнала: «Скачать» у сборки, «Собрать кейсы» у
 * данных под кейс.
 *
 * Просьба владельца 25.09.2026 — «выгрузить кейсы по прогону кнопочкой на
 * прогоне, чтобы сразу». Пачка дня одна и переписывается каждой сборкой,
 * поэтому скачивается копия, которую отложил сам прогон (правило 19в
 * `case-content.md`), — ровно то, что он собрал. Число кейсов на кнопке:
 * сборка идёт по всем проектам, и «54» в строке читалось как «54 кейса».
 *
 * Какой прогон предлагает сборку, решает сервер (`build_cases`): экран видит
 * одну страницу журнала, а «последний без сборки после» считается по всем.
 */
import { Button, Stack, Table, Text } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { startCasesRun } from '../../api/cases';
import { downloadRunPack } from '../../api/ops';
import type { RunRow } from '../../api/types';
import { failureText } from '../cases/failure';
import { saveFile } from '../cases/save';
import { casesCount } from '../format';

/** Ширина подписи отказа — как у прочих длинных текстов журнала. */
const NOTE_WIDTH = 220;

export function RunCases({ run }: { run: RunRow }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const take = useMutation({
    mutationFn: () => downloadRunPack(run.id),
    onMutate: () => setError(null),
    onSuccess: saveFile,
    onError: (failure: unknown) => setError(failureText(failure, 'пачка не скачалась')),
  });

  const build = useMutation({
    mutationFn: startCasesRun,
    onMutate: () => setError(null),
    // Сборка — новый прогон: журнал и «Что дальше» перечитываются и увидят его.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['runs'] }),
    onError: (failure: unknown) => setError(failureText(failure, 'сборка не начата')),
  });

  if (!run.pack && !run.build_cases) return <Table.Td />;

  return (
    <Table.Td ta="center" data-run-cases={run.id}>
      <Stack gap={4} align="center">
        {run.pack && (
          <Button size="xs" variant="light" loading={take.isPending} onClick={() => take.mutate()}>
            Скачать {casesCount(run.pack_cases)}
          </Button>
        )}
        {run.build_cases && (
          <Button size="xs" loading={build.isPending} onClick={() => build.mutate()}>
            Собрать кейсы
          </Button>
        )}
        {error && (
          <Text size="xs" c="red" maw={NOTE_WIDTH}>
            {error}
          </Text>
        )}
      </Stack>
    </Table.Td>
  );
}
