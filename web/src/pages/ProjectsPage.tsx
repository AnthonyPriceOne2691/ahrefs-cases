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

import { fetchProjects } from '../api/projects';

import { Pager } from './projects/Pager';
import { ProjectsBody } from './projects/ProjectsBody';
import { ProjectsFilters } from './projects/ProjectsFilters';

const PAGE_SIZE = 50;

export function ProjectsPage() {
  const navigate = useNavigate();
  const [group, setGroup] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);

  const projects = useQuery({
    queryKey: ['projects', group, query, page],
    queryFn: () => fetchProjects({ group, query, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  /** Смена фильтра возвращает на первую страницу: иначе человек, отфильтровав
   *  на третьей, увидит пустоту и решит, что подходящих проектов нет. */
  function refilter(change: () => void) {
    change();
    setPage(0);
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
              onGroup={(next) => refilter(() => setGroup(next))}
              onQuery={(next) => refilter(() => setQuery(next))}
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
