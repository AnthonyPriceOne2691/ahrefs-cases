/**
 * Пороги: версии и предпросмотр последствий.
 *
 * Предпросмотр — **запрос к серверу**, а не расчёт на экране: тот же проход
 * `verdicts.evaluate`, что и у пересчёта. Вторая реализация на фронте разошлась
 * бы с первой ровно тогда, когда предпросмотру начнут доверять, — на
 * калибровке, где цена ошибки это неверно утверждённый порог.
 */
import { request } from './client';
import type { PreviewView, RecalcView, RulesetRow } from './types';

export function fetchRulesets(limit = 50): Promise<RulesetRow[]> {
  return request<RulesetRow[]>(`/api/rulesets?limit=${limit}`);
}

/** Ничего не записывает: `POST` здесь — потому что считает, а не потому что меняет. */
export function previewRuleset(version: string): Promise<PreviewView> {
  return request<PreviewView>(`/api/rulesets/${encodeURIComponent(version)}/preview`, {
    method: 'POST',
  });
}

/** Сохранить новую версию. Действующей она **не становится**: применение —
 *  отдельный шаг, иначе «посмотреть, что будет» и «сделать так» сливаются. */
export function saveRuleset(version: string, note: string, payload: Record<string, unknown>) {
  return request<RulesetRow>('/api/rulesets', {
    method: 'POST',
    body: { version, note, payload },
  });
}

/** Сделать версию действующей: следующая классификация пойдёт по ней. */
export function activateRuleset(version: string): Promise<RulesetRow> {
  return request<RulesetRow>(`/api/rulesets/${encodeURIComponent(version)}/activate`, {
    method: 'POST',
  });
}

/** Пересчитать вердикты по версии. Ahrefs не трогается — это бесплатно. */
export function recalcRuleset(version: string): Promise<RecalcView> {
  return request<RecalcView>(`/api/rulesets/${encodeURIComponent(version)}/recalc`, {
    method: 'POST',
  });
}
