/**
 * Прогоны: дать список, посмотреть смету, запустить — и увидеть журнал.
 *
 * Раздел собран из двух прежних по просьбе владельца (15.09.2026). Причина
 * видна из самих экранов: «Загрузка» кончалась кнопкой «Запустить прогон», а
 * узнать, что из этого вышло, можно было только в другом разделе — человек
 * начинал работу в одном месте и шёл смотреть результат в другое. Прежняя
 * «Загрузка» даже отсылала туда текстом («Запустить можно на экране
 * „Загрузка“») — две страницы указывали друг на друга.
 *
 * Смета переехала в окно: она отвечает на вопрос «запускать ли», а не «что
 * происходит», и на странице стояла третьей — её пролистывали вместе с ней.
 */
import { Alert, Button, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../api/client';
import { fetchRun, startRun, uploadLink, uploadList } from '../api/intake';
import { fetchRunAuthors, fetchRuns } from '../api/ops';
import type { IntakeReport, RunRow } from '../api/types';
import { usePagedScreen } from '../app/screenState';
import { useStickyFlag } from '../app/stickyFlag';
import { Pager } from '../components/Pager';

import { IntakeOutcome } from './intake/IntakeOutcome';
import { RUNNING } from './intake/RunLine';
import { SourceForm } from './intake/SourceForm';
import { ESTIMATE_KEY, EstimateWindow } from './runs/EstimateWindow';
import { Stage2Launcher } from './runs/Stage2Launcher';
import { JournalFilters, isFiltered } from './runs/JournalFilters';
import type { JournalFilter } from './runs/JournalFilters';
import { NextStep } from './runs/NextStep';
import { RunsTable } from './runs/RunsTable';

const POLL_MS = 5_000;
const OPEN = new Set(['queued', 'running']);

/** Активный прогон ищется по **всем** строкам, а не по первой: номер растёт, а
 *  закончиться прогон может раньше соседа. */
function hasOpenRun(rows: RunRow[] | undefined): boolean {
  return (rows ?? []).some((run) => OPEN.has(run.status));
}

/** Текст отказа берём у сервера: он называет формат, доступ или номер активного
 *  прогона. «Что-то пошло не так» оставило бы человека без следующего шага. */
function failureText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** Журнал и его состояния. Отдельно от страницы — иначе она перерастает планку
 *  длины, и гейт ловит это справедливо (урок L91). */
const PAGE_SIZE = 20;

/** Три состояния журнала, в которых таблицы нет. «Ничего не нашлось» и «ничего
 *  не было» — разные ответы: первый лечится снятием отбора, второй запуском. */
function JournalState({
  pending,
  error,
  rows,
  filtered,
}: {
  pending: boolean;
  error: unknown;
  rows: RunRow[] | undefined;
  filtered: boolean;
}) {
  if (pending) return <Text size="sm">Загружаем журнал…</Text>;
  if (error) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">{failureText(error, 'журнал не загрузился')}</Text>
      </Alert>
    );
  }
  if (rows?.length === 0) {
    return (
      <Alert color="yellow" variant="light">
        <Text size="sm">
          {filtered
            ? 'Под этот отбор прогонов нет. Снимите отбор или возьмите другие даты.'
            : 'Прогонов ещё не было. Дайте список выше и посмотрите смету — запуск там же.'}
        </Text>
      </Alert>
    );
  }
  return null;
}

/**
 * Отбор журнала, живущий в адресе.
 *
 * Отдельным хуком, потому что у него своя работа: читать начальное значение из
 * адреса, писать изменения обратно **одной** правкой и сбрасывать страницу.
 * Внутри экрана это давало ветвление, на которое справедливо ругался гейт
 * сложности.
 */
function useJournalFilter(): {
  page: number;
  setPage: (value: number) => void;
  filter: JournalFilter;
  refine: (next: JournalFilter) => void;
} {
  const { screen, page, setPage } = usePagedScreen();
  const [filter, setFilter] = useState<JournalFilter>({
    startedBy: screen.number('кто', 0) || null,
    since: screen.text('с') || null,
    until: screen.text('по') || null,
  });

  /** Смена отбора возвращает на первую страницу: список становится другой
   *  длины, и третья страница прежнего в новом может не существовать вовсе. */
  const refine = (next: JournalFilter) => {
    setFilter(next);
    setPage(0);
    // Одной правкой адреса: иначе второй вызов перетрёт первый — он читает
    // параметры такими, какими они были до правки.
    screen.set({
      кто: next.startedBy ? String(next.startedBy) : null,
      с: next.since,
      по: next.until,
      page: null,
    });
  };

  return { page, setPage, filter, refine };
}

function Journal() {
  const { page, setPage, filter, refine } = useJournalFilter();

  const authors = useQuery({ queryKey: ['runs', 'authors'], queryFn: fetchRunAuthors });
  const runs = useQuery({
    queryKey: ['runs', 'journal', page, filter],
    queryFn: () => fetchRuns(PAGE_SIZE, page * PAGE_SIZE, filter),
    refetchInterval: (query) => (hasOpenRun(query.state.data) ? POLL_MS : false),
  });

  return (
    <Stack gap="md">
      <JournalFilters filter={filter} authors={authors.data ?? []} onChange={refine} />

      <JournalState
        pending={runs.isPending}
        error={runs.error}
        rows={runs.data}
        filtered={isFiltered(filter)}
      />

      {runs.data && runs.data.length > 0 && <RunsTable rows={runs.data} />}

      {/* Листалка показывается, только когда есть что листать: на одной
          неполной странице две серые кнопки — шум. */}
      {(page > 0 || runs.data?.length === PAGE_SIZE) && (
        <Pager page={page} full={runs.data?.length === PAGE_SIZE} onChange={setPage} />
      )}

      {hasOpenRun(runs.data) && (
        <Text size="xs" c="dimmed">
          Прогон идёт: журнал обновляется сам.
        </Text>
      )}
    </Stack>
  );
}

export function RunsPage() {
  const queryClient = useQueryClient();
  const [report, setReport] = useState<IntakeReport | null>(null);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [showEstimate, setShowEstimate] = useStickyFlag('смета');

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
      await queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
    onError: (error: unknown) => setStartError(failureText(error, 'прогон не начат')),
  });

  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Прогоны</Title>

        <Paper className="glass" p="lg">
          <Stack gap="md">
            <SourceForm
              busy={accept.isPending}
              error={intakeError}
              onSubmit={(source) => accept.mutate(source)}
            />
            <Group>
              <Button onClick={() => setShowEstimate(true)}>Смета и запуск</Button>
              <Stage2Launcher run={run.data ?? null} onStarted={setRunId} />
            </Group>
            <NextStep />
          </Stack>
        </Paper>

        {report && (
          <Paper className="glass" p="lg">
            <IntakeOutcome report={report} />
          </Paper>
        )}

        <Paper className="glass" p="lg">
          <Stack gap="md">
            <Title order={4}>Журнал прогонов</Title>
            <Journal />
          </Stack>
        </Paper>

        <EstimateWindow
          opened={showEstimate}
          onClose={() => setShowEstimate(false)}
          run={run.data ?? null}
          starting={launch.isPending}
          startError={startError}
          onStart={() => launch.mutate()}
        />
      </Stack>
    </Container>
  );
}
