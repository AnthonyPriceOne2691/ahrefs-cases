/**
 * Экран проектов: что получилось из загруженного списка.
 *
 * Состояний пять, и у каждого свой текст: грузится, есть строки, пусто по
 * фильтру, пусто вообще, отказ сервера.
 */
import { Container, Paper, Stack, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { usePagedScreen } from '../app/screenState';
import { Pager } from '../components/Pager';
import { fetchProjects } from '../api/projects';

import { ProjectsBody } from './projects/ProjectsBody';
import { ProjectsFilters } from './projects/ProjectsFilters';

const PAGE_SIZE = 20;
/** Двадцать строк — столько видно на экране без прокрутки таблицы. Пятьдесят
 *  прокручивались, и листалка внизу оказывалась за краем: человек про неё
 *  узнавал, только домотав до конца. */

export function ProjectsPage() {
  const navigate = useNavigate();
  // Фильтры и страница живут в адресе: F5 не стирает работу, «назад»
  // возвращает к тому, что человек видел, а ссылку можно переслать.
  const { screen, page, setPage } = usePagedScreen();
  const [group, setGroup] = useState<string | null>(screen.text('group') || null);
  const [query, setQuery] = useState(screen.text('query'));

  const projects = useQuery({
    queryKey: ['projects', group, query, page],
    queryFn: () => fetchProjects({ group, query, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  /** Смена фильтра возвращает на первую страницу: иначе человек, отфильтровав
   *  на третьей, увидит пустоту и решит, что подходящих проектов нет.
   *
   *  Одной правкой адреса, а не двумя: второй вызов читал бы параметры
   *  такими, какими они были до первого, и сбрасывал бы сам фильтр. */
  function refilter(patch: { group?: string | null; query?: string }) {
    if (patch.group !== undefined) setGroup(patch.group);
    if (patch.query !== undefined) setQuery(patch.query);
    setPage(0);
    screen.set({ ...patch, page: null });
  }

  const rows = projects.data ?? [];
  const filtered = Boolean(group) || query.trim().length > 0;

  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Проекты</Title>
        <Paper className="glass" p="lg">
          <Stack gap="md">
            <ProjectsFilters
              group={group}
              query={query}
              onGroup={(next) => refilter({ group: next })}
              onQuery={(next) => refilter({ query: next })}
            />

            <ProjectsBody
              rows={projects.data}
              loading={projects.isPending}
              error={projects.isError ? projects.error : null}
              filtered={filtered}
              onOpen={(project) => navigate(`/projects/${project.id}`)}
            />

            {(page > 0 || rows.length === PAGE_SIZE) && (
              <Pager page={page} full={rows.length === PAGE_SIZE} onChange={setPage} />
            )}
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
