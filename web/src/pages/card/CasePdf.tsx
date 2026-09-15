/**
 * Кейс этого проекта: скачать файл, не уходя с карточки.
 *
 * До 15.09.2026 файл можно было забрать только с экрана «Кейсы» — то есть
 * человек, разобравшийся в карточке, почему группа именно такая, уходил искать
 * тот же проект в другой таблице. Кнопка отвечает на вопрос там, где он
 * возникает.
 *
 * Собирать кейс отсюда НЕЛЬЗЯ, и это не упущение: сборка идёт пачкой по текущим
 * вердиктам одним прогоном (`/api/runs/cases`), и вторая дверь к расходу,
 * придуманная на фронте, разошлась бы с этим замком.
 */
import { Button, Group, Text } from '@mantine/core';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { downloadCase, fetchCasesOfProject } from '../../api/cases';
import type { CaseRow } from '../../api/types';
import { failureText } from '../cases/failure';
import { saveFile } from '../cases/save';

/** Почему скачать нельзя — словами, а не серой кнопкой без объяснения. */
function obstacle(rows: CaseRow[] | undefined): string | null {
  if (rows === undefined) return null;
  const row = rows[0];
  if (row === undefined) return 'Кейс ещё не собран. Сборка идёт пачкой на экране «Кейсы».';
  if (row.filename === null) return 'Кейс в базе есть, а файла к нему нет — собрать заново.';
  return null;
}

export function CasePdf({ projectId }: { projectId: number }) {
  const [error, setError] = useState<string | null>(null);
  const cases = useQuery({
    queryKey: ['project', projectId, 'case'],
    queryFn: () => fetchCasesOfProject(projectId),
    enabled: Number.isFinite(projectId),
  });

  // `ready` — кейс, который действительно можно скачать. Проверка тут одна на
  // всех: кнопка выключена ровно тогда, когда качать нечего, и обработчику
  // не приходится доверять этому на слово.
  const row = cases.data?.[0];
  const ready = row?.filename ? row : null;
  const why = obstacle(cases.data);

  const take = useMutation({
    mutationFn: () => {
      if (ready === null) throw new Error('кейса с файлом нет');
      return downloadCase(ready.id, ready.filename ?? `кейс-${ready.id}.pdf`);
    },
    onMutate: () => setError(null),
    onSuccess: saveFile,
    onError: (failure: unknown) => setError(failureText(failure, 'кейс не скачался')),
  });

  return (
    <Group gap="sm" align="center" wrap="wrap">
      <Button
        variant="light"
        loading={take.isPending}
        disabled={cases.isPending || why !== null}
        onClick={() => take.mutate()}
      >
        Скачать PDF
      </Button>
      {why && (
        <Text size="sm" c="dimmed">
          {why}
        </Text>
      )}
      {error && (
        <Text size="sm" c="red">
          {error}
        </Text>
      )}
    </Group>
  );
}
