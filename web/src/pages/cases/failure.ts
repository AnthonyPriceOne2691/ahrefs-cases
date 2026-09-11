/**
 * Текст отказа для человека.
 *
 * Слова берёт сервер: он называет, файла нет, права не хватает или прогон уже
 * идёт. Общее «что-то пошло не так» оставило бы человека без следующего шага —
 * то же правило, по которому различаются исходы в клиенте API.
 */
import { ApiError } from '../../api/client';

export function failureText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}
