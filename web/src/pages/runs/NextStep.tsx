/**
 * «Что дальше» — следующая кнопка по последнему прогону сервиса.
 *
 * Кейсы получаются тремя кнопками на двух экранах: «Смета и запуск» (шаг 1 —
 * группы), «Дособрать кандидатов» (шаг 2 и данные под кейс) и «Пересобрать
 * кейсы» на экране «Кейсы», где потом «Скачать ZIP». Каждая кнопка подписана,
 * но порядок не назван нигде — и 25.09.2026 после двух прогонов шага 1 до PDF
 * на проде не дошёл никто.
 *
 * Прогон берётся последний **по сервису**, а не свой: группы, купленные данные
 * и пачка у всех общие, значит и следующий шаг общий. Упавший, отменённый и
 * отклонённый прогон подсказки не получают: причину говорит журнал, а совет,
 * не знающий причины, указал бы не туда.
 */
import { Alert, Anchor, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { fetchRuns } from '../../api/ops';
import type { RunRow } from '../../api/types';
import { RUNNING } from '../intake/RunLine';
import { runWord, stageWord } from '../status';

const POLL_MS = 5_000;

/** Конец шага: «частично» — тоже конец, недособранное видно в журнале. */
const FINISHED = new Set(['done', 'partial']);

/** Следующий шаг после каждой ступени и нужна ли ссылка на «Кейсы». */
const AFTER: Record<string, { next: string; toCases: boolean }> = {
  stage1: {
    next: 'Дальше — кнопка «Дособрать кандидатов» выше: шаг 2 и данные под кейс для хороших и средних. Окно покажет кандидатов и цену до запуска.',
    toCases: false,
  },
  stage2: {
    next: 'Если есть хорошие и средние, следом сам идёт прогон «данные под кейс», а после него кейсы собираются на экране «Кейсы» кнопкой «Пересобрать кейсы».',
    toCases: true,
  },
  case_data: {
    next: 'Осталось собрать кейсы: на экране «Кейсы» кнопка «Пересобрать кейсы», когда сборка закончится — «Скачать ZIP».',
    toCases: true,
  },
  cases: {
    next: 'Кейсы на экране «Кейсы»: «Скачать ZIP» — пачка целиком, «Скачать PDF» — по одному.',
    toCases: true,
  },
};

export interface NextHint {
  text: string;
  toCases: boolean;
}

export function nextStep(run: RunRow | null): NextHint | null {
  const after = run ? AFTER[run.stage] : undefined;
  if (!run || !after) return null;
  const title = `Прогон №${run.id} — ${stageWord(run.stage)}`;
  if (RUNNING.has(run.status)) {
    return {
      text: `${title} — ${runWord(run.status)}. Когда он закончится, здесь появится следующий шаг.`,
      toCases: false,
    };
  }
  if (!FINISHED.has(run.status)) return null;
  const partial = run.status === 'partial' ? ' Что не собралось и почему — в журнале ниже.' : '';
  return {
    text: `${title} — ${runWord(run.status)}.${partial} ${after.next}`,
    toCases: after.toCases,
  };
}

export function NextStep() {
  const latest = useQuery({
    queryKey: ['runs', 'latest'],
    queryFn: () => fetchRuns(1, 0),
    // Пока прогон идёт, подсказка сменится сама: человек, нажавший кнопку, не
    // должен перезагружать страницу, чтобы узнать следующий шаг.
    refetchInterval: (query) =>
      RUNNING.has(query.state.data?.[0]?.status ?? '') ? POLL_MS : false,
  });
  const hint = nextStep(latest.data?.[0] ?? null);
  if (!hint) return null;

  return (
    <Alert variant="light" title="Что дальше" data-next-step>
      <Stack gap={4}>
        <Text size="sm">{hint.text}</Text>
        {hint.toCases && (
          <Anchor component={Link} to="/cases" size="sm">
            Перейти к кейсам
          </Anchor>
        )}
      </Stack>
    </Alert>
  );
}
