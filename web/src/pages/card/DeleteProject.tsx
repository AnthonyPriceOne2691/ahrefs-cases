/**
 * Удаление проекта — с подтверждением на месте, по образцу удаления человека.
 *
 * Удаление жёсткое (решение владельца 24.09.2026): уходят купленные ряды,
 * вердикты, кейсы и их файлы, и вернуть их можно только новой покупкой. Поэтому
 * подтверждение называет **последствия числами** — их считает сервер
 * (`GET …/deletion`), экран их не пересчитывает (урок L78). Спрашиваем по
 * нажатию: карточку открывают все, удаляют единицы.
 *
 * Не попапом: попапы Mantine в jsdom рендерятся секундами, а необратимый шаг
 * обязан быть проверен тестом (урок L76).
 */
import { Alert, Anchor, Button, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { deleteProject, fetchDeletion } from '../../api/projects';
import type { ProjectDeletion } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { failureText } from '../cases/failure';
import { num } from '../format';

interface Props {
  projectId: number;
  domain: string;
  onDeleted: (result: ProjectDeletion) => void;
}

/** Кнопка — только тому, у кого есть право: итог из `/me` с личными решениями. */
export function DeleteProject(props: Props) {
  const { can } = useAuth();
  return can('delete_projects') ? <AskAndDelete {...props} /> : null;
}

function AskAndDelete({ projectId, domain, onDeleted }: Props) {
  const [asked, setAsked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preview = useQuery({
    queryKey: ['project', projectId, 'deletion'],
    queryFn: () => fetchDeletion(projectId),
    enabled: asked,
    // Числа — на момент вопроса: между двумя вопросами мог пройти прогон.
    staleTime: 0,
  });
  const drop = useMutation({
    mutationFn: () => deleteProject(projectId),
    onMutate: () => setError(null),
    onSuccess: onDeleted,
    onError: (failure: unknown) => setError(failureText(failure, 'проект не удалён')),
  });

  if (!asked) {
    return (
      <Group>
        <Button size="compact-sm" variant="light" color="red" onClick={() => setAsked(true)}>
          Удалить проект
        </Button>
      </Group>
    );
  }

  return (
    <Alert color="red" variant="light" data-delete={projectId}>
      <Text size="sm" fw={600}>
        Удалить {domain}? Вернуть его будет нельзя.
      </Text>
      {preview.data && <Consequences view={preview.data} />}
      {preview.isPending && <Text size="sm">Считаем, что уйдёт…</Text>}
      {preview.isError && (
        <Text size="sm">{failureText(preview.error, 'не удалось узнать, что уйдёт')}</Text>
      )}
      <Group mt="sm">
        <Button
          size="compact-sm"
          color="red"
          disabled={!preview.data}
          loading={drop.isPending}
          onClick={() => drop.mutate()}
        >
          Да, удалить
        </Button>
        <Button size="compact-sm" variant="subtle" onClick={() => setAsked(false)}>
          Отмена
        </Button>
      </Group>
      {error && (
        <Text size="sm" c="red" mt="xs">
          {error}
        </Text>
      )}
    </Alert>
  );
}

/** Что уйдёт и что останется — числами сервера. */
function Consequences({ view }: { view: ProjectDeletion }) {
  return (
    <Stack gap={4} mt="xs">
      <Text size="sm">
        Уйдут: точек рядов: {num(view.metric_points)} — за них платили, повторная загрузка купит их
        заново; вердиктов: {num(view.verdicts)}; кейсов: {num(view.cases)}; файлов PDF:{' '}
        {num(view.files)}.
      </Text>
      <Text size="sm">
        Останутся: строк журнала прогонов: {num(view.run_items)} — там домен будет подписан «(проект
        удалён)»; расход units
        {view.twin_campaigns > 0 &&
          `; другие кампании этого сайта: ${num(view.twin_campaigns)} — у них свои данные`}
        .
      </Text>
      {view.pack_blocked && (
        <Text size="sm">
          В свежей пачке есть кейс этого проекта: пачка кейсов не скачается до пересборки.
        </Text>
      )}
    </Stack>
  );
}

/**
 * Итог удаления и что сделать с кэшем. Карточка проекта стирается из него, а
 * списки перечитываются при следующем заходе: иначе удалённый ещё полминуты
 * всплывал бы в них из кэша (`staleTime` приложения — 30 с).
 */
export function useDeletedProject(projectId: number) {
  const queryClient = useQueryClient();
  const [deleted, setDeleted] = useState<ProjectDeletion | null>(null);
  function forget(result: ProjectDeletion) {
    setDeleted(result);
    queryClient.removeQueries({ queryKey: ['project', projectId] });
    for (const key of ['projects', 'cases', 'runs']) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  }
  return { deleted, forget };
}

/** Итог на месте карточки: карточки больше нет, а что ушло — сказано числами ответа. */
export function ProjectDeleted({ result }: { result: ProjectDeletion }) {
  return (
    <Container size="lg">
      <Paper className="glass" p="lg" data-deleted={result.project_id}>
        <Stack gap="sm">
          <Title order={3}>Проект {result.domain} удалён</Title>
          <Text size="sm">
            Ушло: точек рядов: {num(result.metric_points)}; вердиктов: {num(result.verdicts)};
            кейсов: {num(result.cases)}; файлов PDF: {num(result.files)}.
          </Text>
          <Text size="sm">
            Осталось: строк журнала прогонов: {num(result.run_items)} — домен там подписан «(проект
            удалён)»; расход units не тронут.
          </Text>
          {result.pack_blocked && (
            <Text size="sm">
              Пачку кейсов пересоберите на экране «Кейсы» — до этого она не скачивается.
            </Text>
          )}
          <Anchor component={Link} to="/projects" size="sm">
            ← к списку проектов
          </Anchor>
        </Stack>
      </Paper>
    </Container>
  );
}
