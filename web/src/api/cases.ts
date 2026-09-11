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

export function fetchCases(limit = 50): Promise<CaseRow[]> {
  return request<CaseRow[]>(`/api/cases?limit=${limit}`);
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

export function downloadPack(fallbackName: string) {
  return download('/api/cases/pack/download', fallbackName);
}
