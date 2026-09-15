/**
 * Библиотека кейсов и пачка: то, ради чего сервис существует.
 *
 * Кейсы не собираются по одному: сборка идёт пачкой по текущим вердиктам, и
 * запускает её тот же прогон, что и всё остальное (`/api/runs/cases`) — с тем
 * же замком на второй одновременный. Отдельной кнопки «пересобрать этот кейс»
 * здесь нет нарочно: в API её нет, а придуманная на фронте она стала бы второй
 * дверью к расходу.
 */
import { download, request } from './client';
import type { CaseRow, PackView, RunStarted } from './types';

/** Библиотека. По умолчанию — свежий кейс каждого проекта: пересборка добавляет
 *  версию, и без этого один проект занимает десяток строк.
 *
 *  `offset` был у сервера с самого начала, а фронт его не спрашивал — и
 *  показывал первые пятьдесят строк как всю библиотеку. */
export function fetchCases(limit = 50, allVersions = false, offset = 0): Promise<CaseRow[]> {
  return request<CaseRow[]>(
    `/api/cases?limit=${limit}&offset=${offset}&all_versions=${allVersions}`,
  );
}

/** Кейсы одного проекта — свежий на каждую сборку. Спрашивает карточка проекта:
 *  перебирать ради одной строки всю библиотеку она не должна (см. `project_id`
 *  в `api/routers/cases.py`). */
export function fetchCasesOfProject(projectId: number): Promise<CaseRow[]> {
  return request<CaseRow[]>(`/api/cases?limit=1&project_id=${projectId}`);
}

export function fetchPack(): Promise<PackView> {
  return request<PackView>('/api/cases/pack');
}

export function startCasesRun(): Promise<RunStarted> {
  return request<RunStarted>('/api/runs/cases', { method: 'POST' });
}

/** Один кейс. Имя берём у сервера: под ним файл уйдёт клиенту. */
export function downloadCase(caseId: number, fallbackName: string) {
  return download(`/api/cases/${caseId}/download`, fallbackName);
}

/** Выбранные кейсы одним архивом.
 *
 *  Пачкой отдельных загрузок это сделать нельзя: браузер разрешает вкладке одну
 *  загрузку за жест человека и остальные обрывает молча — из десяти выбранных
 *  дошли бы два, и о восьми никто бы не узнал. */
export function downloadSelection(ids: number[], fallbackName: string) {
  const query = ids.map((id) => `ids=${id}`).join('&');
  return download(`/api/cases/selection/download?${query}`, fallbackName);
}

export function downloadPack(fallbackName: string) {
  return download('/api/cases/pack/download', fallbackName);
}
