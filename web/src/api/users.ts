/**
 * Люди и права.
 *
 * Справочник прав спрашивается у сервера, а не хранится здесь: права проверяют
 * роутеры, и вторая таблица на фронте разошлась бы с первой в тот день, когда
 * правят первую.
 */
import { request } from './client';
import type { RightsCatalog, UserPatch, UserRow, UserWithPassword } from './types';

export function fetchUsers(limit = 50): Promise<UserRow[]> {
  return request<UserRow[]>(`/api/users?limit=${limit}`);
}

export function fetchRights(): Promise<RightsCatalog> {
  return request<RightsCatalog>('/api/users/rights');
}

/** Завести человека. Пароль генерирует сервер и отдаёт **один раз**. */
export function createUser(email: string, fullName: string, group: string) {
  return request<UserWithPassword>('/api/users', {
    method: 'POST',
    body: { email, full_name: fullName, group },
  });
}

/** Изменить то, что назвали. Незаданное поле сервер не трогает. */
export function patchUser(userId: number, patch: UserPatch): Promise<UserRow> {
  return request<UserRow>(`/api/users/${userId}`, { method: 'PATCH', body: patch });
}

export function resetPassword(userId: number): Promise<UserWithPassword> {
  return request<UserWithPassword>(`/api/users/${userId}/password`, { method: 'POST' });
}
