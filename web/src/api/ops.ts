/**
 * Операционные запросы: журнал прогонов, расход units, алерты.
 *
 * Три запроса рядом, потому что отвечают на один вопрос оператора — «что
 * сейчас с сервисом и сколько денег осталось».
 */
import { request } from './client';
import type { AlertView, RunAuthor, RunCard, RunRow, UsageView } from './types';

/** Журнал: свежие сверху. Потолок выдачи держит сервер, здесь — размер страницы. */
/** Отбор журнала. Пустое поле — «без отбора», а не «пусто»: `null` не уезжает
 *  в адрес запроса вовсе. */
export interface RunsFilter {
  startedBy?: number | null;
  since?: string | null;
  until?: string | null;
}

export function fetchRuns(limit = 20, offset = 0, filter: RunsFilter = {}): Promise<RunRow[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filter.startedBy) query.set('started_by', String(filter.startedBy));
  if (filter.since) query.set('since', filter.since);
  if (filter.until) query.set('until', filter.until);
  return request<RunRow[]>(`/api/runs?${query.toString()}`);
}

/** Кем запускались прогоны — список для отбора. Спрашивается у сервера, а не
 *  собирается по видимой странице: отбор «показать Петра» исчезал бы, стоило
 *  пролистнуть туда, где Петра нет. */
export function fetchRunAuthors(): Promise<RunAuthor[]> {
  return request<RunAuthor[]>('/api/runs/authors');
}

/** Карточка прогона: та же строка плюс судьба каждого домена.
 *
 * Спрашивается **по требованию**, а не в журнале: список судеб нужен тому, кто
 * уже увидел «пропущено 2» и спросил «кого именно», а журнал опрашивается по
 * таймеру, пока идёт прогон.
 */
export function fetchRun(runId: number): Promise<RunCard> {
  return request<RunCard>(`/api/runs/${runId}`);
}

export function fetchUsage(): Promise<UsageView> {
  return request<UsageView>('/api/usage');
}

export function fetchAlerts(): Promise<AlertView[]> {
  return request<AlertView[]>('/api/alerts');
}
