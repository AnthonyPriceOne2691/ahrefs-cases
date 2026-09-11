/**
 * Список проектов. Фильтры уходят **на сервер**, а не применяются к странице.
 *
 * Сервер отдаёт не больше сотни строк за раз; фильтр по видимым строкам сказал
 * бы «хороших нет», когда они на второй странице.
 */
import { request } from './client';
import type { ChartBlock, ProjectCard, ProjectRow, ProjectsQuery } from './types';

export function fetchProjects(params: ProjectsQuery): Promise<ProjectRow[]> {
  const search = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.group) search.set('group', params.group);
  if (params.query?.trim()) search.set('query', params.query.trim());
  return request<ProjectRow[]>(`/api/projects?${search.toString()}`);
}

export function fetchProjectCard(projectId: number): Promise<ProjectCard> {
  return request<ProjectCard>(`/api/projects/${projectId}`);
}

/** Шаг кривой. Свёртка бесплатна и делается на сервере: правило зависит от
 *  природы метрики (поток складывается, запас берётся на конец периода). */
export type Grouping = 'month' | 'quarter' | 'year';

export function fetchProjectCharts(
  projectId: number,
  grouping: Grouping = 'month',
): Promise<ChartBlock[]> {
  return request<ChartBlock[]>(`/api/projects/${projectId}/charts?grouping=${grouping}`);
}
