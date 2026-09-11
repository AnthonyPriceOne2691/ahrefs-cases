/**
 * Вызовы экрана загрузки: дать список, узнать цену, запустить прогон.
 *
 * Смета считается **на сервере** и здесь только показывается. Считать её второй
 * раз на фронте значило бы завести вторую модель цены: она зависит от того, что
 * уже собрано, от выбранной схемы и от активной версии порогов — и разошлась бы
 * с первой молча, в деньгах.
 */
import { request } from './client';
import type { IntakeReport, RunEstimate, RunRow, RunStarted } from './types';

export function uploadList(file: File): Promise<IntakeReport> {
  return request<IntakeReport>(`/api/intake/file?filename=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    raw: file,
  });
}

export function uploadLink(url: string): Promise<IntakeReport> {
  return request<IntakeReport>('/api/intake/link', { method: 'POST', body: { url } });
}

export function fetchEstimate(): Promise<RunEstimate> {
  return request<RunEstimate>('/api/runs/estimate');
}

export function startRun(): Promise<RunStarted> {
  return request<RunStarted>('/api/runs', { method: 'POST' });
}

export function fetchRun(runId: number): Promise<RunRow> {
  return request<RunRow>(`/api/runs/${runId}`);
}
