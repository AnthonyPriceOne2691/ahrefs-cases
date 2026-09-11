/**
 * Карточка проекта: почему группа именно такая.
 *
 * Таблица показывает результат, карточка — основание: точки А и Б, условия
 * вердикта и кривые. Числа берутся из **записанного** вердикта, а не считаются
 * заново: экран обязан отвечать то же, что таблица и PDF (урок L41).
 */
import { Alert, Container, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { fetchProjectCard, fetchProjectCharts } from '../api/projects';

import { CardHeader } from './card/CardHeader';
import { Charts } from './card/Charts';
import { Comparison } from './card/Comparison';
import { Hero } from './card/Hero';
import { Reasons } from './card/Reasons';

const FOOTNOTE =
  'Числа — оценки Ahrefs, а не фактические визиты. Точки А и Б усреднены по окнам ' +
  'версии порогов, поэтому отличаются от последнего измеренного месяца.';

export function ProjectCardPage() {
  const { projectId } = useParams();
  const id = Number(projectId);

  const card = useQuery({
    queryKey: ['project', id],
    queryFn: () => fetchProjectCard(id),
    enabled: Number.isFinite(id),
  });
  const charts = useQuery({
    queryKey: ['project', id, 'charts'],
    queryFn: () => fetchProjectCharts(id),
    enabled: Number.isFinite(id),
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

        {verdict ? (
          <>
            <Paper className="glass" p="lg">
              <Stack gap="md">
                <Hero rows={verdict.comparison} />
                <Comparison rows={verdict.comparison} />
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

        <Paper className="glass" p="lg">
          <Stack gap="sm">
            <Title order={3}>Динамика</Title>
            {charts.isPending && <Text size="sm">Рисуем кривые…</Text>}
            {charts.data && <Charts blocks={charts.data} />}
          </Stack>
        </Paper>

        <Text size="xs" c="dimmed">
          {FOOTNOTE}
        </Text>
      </Stack>
    </Container>
  );
}
