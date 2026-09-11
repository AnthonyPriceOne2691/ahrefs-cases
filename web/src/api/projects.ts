/**
 * Список проектов. Фильтры уходят **на сервер**, а не применяются к странице.
 *
 * Сервер отдаёт не больше сотни строк за раз; фильтр по видимым строкам сказал
 * бы «хороших нет», когда они на второй странице.
 */
import { request } from './client';
import type { ProjectRow, ProjectsQuery } from './types';

export function fetchProjects(params: ProjectsQuery): Promise<ProjectRow[]> {
  const search = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.group) search.set('group', params.group);
  if (params.query?.trim()) search.set('query', params.query.trim());
  return request<ProjectRow[]>(`/api/projects?${search.toString()}`);
}
