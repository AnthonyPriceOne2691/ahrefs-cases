/**
 * Карточка проекта: почему группа именно такая.
 *
 * Таблица показывает результат, карточка — основание: точки А и Б, условия
 * вердикта и кривые. Числа берутся из **записанного** вердикта, а не считаются
 * заново: экран обязан отвечать то же, что таблица и PDF (урок L41).
 */
import { Alert, Container, Paper, Stack, Text, Title } from '@mantine/core';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { fetchProjectCard, fetchProjectCharts } from '../api/projects';
import type { Grouping } from '../api/projects';

import { CardHeader } from './card/CardHeader';
import { CasePdf } from './card/CasePdf';
import { Comparison } from './card/Comparison';
import { Dynamics } from './card/Dynamics';
import { Hero } from './card/Hero';
import { Reasons } from './card/Reasons';
import { SourceMismatch } from './card/SourceMismatch';

const FOOTNOTE =
  'Числа — оценки Ahrefs, а не фактические визиты. Точки А и Б усреднены по окнам ' +
  'версии порогов, поэтому отличаются от последнего измеренного месяца.';

export function ProjectCardPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  // Шаг кривой — состояние экрана, а не вердикта: таблицу А → Б и условия он
  // не трогает, они принадлежат записанному решению.
  const [grouping, setGrouping] = useState<Grouping>('month');

  const card = useQuery({
    queryKey: ['project', id],
    queryFn: () => fetchProjectCard(id),
    enabled: Number.isFinite(id),
  });
  const charts = useQuery({
    queryKey: ['project', id, 'charts', grouping],
    queryFn: () => fetchProjectCharts(id, grouping),
    enabled: Number.isFinite(id),
    // Прежние кривые остаются на экране, пока грузятся новые. Без этого смена
    // шага меняла ключ запроса, `data` становилась `undefined`, и блок «Динамика»
    // исчезал целиком — вместе с переключателем, который только что нажали.
    // Страница при этом схлопывалась на высоту одной строки, и браузер уводил
    // прокрутку наверх, хотя кривые внизу: человек нажимал «квартал» и терял
    // из виду и графики, и саму кнопку (найдено владельцем 15.09.2026).
    placeholderData: keepPreviousData,
  });

  if (card.isPending) {
    return (
      <Container size="lg">
        <Text size="sm">Загружаем карточку…</Text>
      </Container>
    );
  }

  if (card.isError) {
    const failure = card.error;
    return (
      <Container size="lg">
        <Alert color="red" variant="light">
          <Text size="sm">
            {failure instanceof ApiError ? failure.message : 'карточка не загрузилась'}
          </Text>
        </Alert>
      </Container>
    );
  }

  const verdict = card.data.verdict;

  return (
    <Container size="lg">
      <Stack gap="lg">
        <CardHeader card={card.data} />

        <CasePdf projectId={id} />

        <SourceMismatch reason={card.data.source_mismatch} />

        {verdict ? (
          <>
            <Paper className="glass" p="lg">
              <Stack gap="md">
                <Hero rows={verdict.comparison} />
                <Comparison rows={verdict.comparison} note={verdict.points_note} />
              </Stack>
            </Paper>

            <Paper className="glass" p="lg">
              <Stack gap="sm">
                <Title order={3}>Почему эта группа</Title>
                <Reasons rows={verdict.reasons} />
              </Stack>
            </Paper>
          </>
        ) : (
          <Paper className="glass" p="lg">
            <Alert color="yellow" variant="light">
              <Text size="sm">
                Проект не классифицирован действующей версией порогов. Запустите классификацию — она
                бесплатна и считает по уже собранным данным.
              </Text>
            </Alert>
          </Paper>
        )}

        <Dynamics
          blocks={charts.data}
          pending={charts.isPending}
          stale={charts.isPlaceholderData}
          grouping={grouping}
          onGrouping={setGrouping}
        />

        <Text size="xs" c="dimmed">
          {FOOTNOTE}
        </Text>
      </Stack>
    </Container>
  );
}
