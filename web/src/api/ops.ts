/**
 * Операционные запросы: журнал прогонов, расход units, алерты.
 *
 * Три запроса рядом, потому что отвечают на один вопрос оператора — «что
 * сейчас с сервисом и сколько денег осталось».
 */
import { request } from './client';
import type { AlertView, RunRow, UsageView } from './types';

/** Журнал: свежие сверху. Потолок выдачи держит сервер, здесь — размер страницы. */
export function fetchRuns(limit = 20): Promise<RunRow[]> {
  return request<RunRow[]>(`/api/runs?limit=${limit}`);
}

export function fetchUsage(): Promise<UsageView> {
  return request<UsageView>('/api/usage');
}

export function fetchAlerts(): Promise<AlertView[]> {
  return request<AlertView[]>('/api/alerts');
}
