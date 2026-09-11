/**
 * Люди и права.
 *
 * Справочник прав спрашивается у сервера, а не хранится здесь: права проверяют
 * роутеры, и вторая таблица на фронте разошлась бы с первой в тот день, когда
 * правят первую.
 */
import { request } from './client';
import type { RightsCatalog, UserRow } from './types';

export function fetchUsers(limit = 50): Promise<UserRow[]> {
  return request<UserRow[]>(`/api/users?limit=${limit}`);
}

export function fetchRights(): Promise<RightsCatalog> {
  return request<RightsCatalog>('/api/users/rights');
}
