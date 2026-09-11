/**
 * Пороги: версии.
 *
 * Версия неизменяема — правка это новая версия: вердикты ссылаются на версию,
 * и правка задним числом сделала бы прошлые решения необъяснимыми.
 */
import { request } from './client';
import type { RulesetRow } from './types';

export function fetchRulesets(limit = 50): Promise<RulesetRow[]> {
  return request<RulesetRow[]>(`/api/rulesets?limit=${limit}`);
}
