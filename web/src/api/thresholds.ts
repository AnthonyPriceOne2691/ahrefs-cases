/**
 * Пороги: версии и предпросмотр последствий.
 *
 * Предпросмотр — **запрос к серверу**, а не расчёт на экране: тот же проход
 * `verdicts.evaluate`, что и у пересчёта. Вторая реализация на фронте разошлась
 * бы с первой ровно тогда, когда предпросмотру начнут доверять, — на
 * калибровке, где цена ошибки это неверно утверждённый порог.
 */
import { request } from './client';
import type { PreviewView, RulesetRow } from './types';

export function fetchRulesets(limit = 50): Promise<RulesetRow[]> {
  return request<RulesetRow[]>(`/api/rulesets?limit=${limit}`);
}

/** Ничего не записывает: `POST` здесь — потому что считает, а не потому что меняет. */
export function previewRuleset(version: string): Promise<PreviewView> {
  return request<PreviewView>(`/api/rulesets/${encodeURIComponent(version)}/preview`, {
    method: 'POST',
  });
}
