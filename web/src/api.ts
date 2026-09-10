/** Тонкий слой доступа к API. Адрес не хардкодится — ходим через прокси Vite. */

export type HealthResponse = {
  status: 'ok' | 'unavailable';
  provider: string;
  migration?: string;
  reason?: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health');
  // 503 — законный ответ этого эндпоинта, а не сбой запроса: тело в нём есть,
  // и именно оно объясняет, что с сервисом. Бросать здесь исключение значило бы
  // потерять причину.
  return (await response.json()) as HealthResponse;
}
