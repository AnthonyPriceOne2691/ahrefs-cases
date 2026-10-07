/**
 * Бриф копирайтеру: каталог пунктов шаблона и правка брифа проекта.
 *
 * Каталог — с сервера: поля и списки описаны там один раз, и форма, приём файла
 * и лист PDF читают одно и то же.
 */
import { request } from './client';
import type { BriefCatalog, BriefPatch, BriefView } from './types';

/** Каталог проверяется формой: чужой ответ, принятый за каталог, ронял бы карточку
 *  целиком, а не один блок брифа (урок L23 — чужая форма не притворяется нашей). */
export async function fetchBriefFields(): Promise<BriefCatalog> {
  const catalog = await request<Partial<BriefCatalog> | null>('/api/brief-fields');
  if (!Array.isArray(catalog?.sections) || !Array.isArray(catalog?.fields)) {
    throw new Error('пункты брифа пришли не той формы');
  }
  return { sections: catalog.sections, fields: catalog.fields };
}

export function saveBrief(projectId: number, patch: BriefPatch): Promise<BriefView> {
  return request<BriefView>(`/api/projects/${projectId}/brief`, { method: 'PATCH', body: patch });
}
