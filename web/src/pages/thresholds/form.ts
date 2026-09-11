/**
 * Поля формы порогов и перенос их в `payload`.
 *
 * Правятся только те значения, что **решают группу** (решение владельца
 * 11.09.2026): условия «хорошего» и «среднего», пригодность, ограничитель.
 * Окна точек А и Б и веса счёта остаются на просмотр — они меняют смысл самих
 * данных, а не границу, и ошибка в них тихо переписала бы все числа А → Б.
 *
 * Отсюда главное свойство переноса: **правка идёт поверх существующей версии**.
 * Непоказанные поля переезжают в новую версию как есть, а не теряются и не
 * заменяются умолчаниями — иначе форма молча сбрасывала бы то, чего не знает.
 */
import { readRules } from './rules';

/** Значение поля: пустая строка — «не задано», а не ноль (урок L95). */
export type Field = number | '';

export interface GroupFields {
  growthPctMin: Field;
  growthAbsMin: Field;
  growthPctMax: Field;
  orHighPctLowAbs: boolean;
  supportingRequired: number;
  refdomainsPctMin: Field;
  kwTop10PctMin: Field;
  minMonths: Field;
}

export interface FormValues {
  version: string;
  note: string;
  good: GroupFields;
  medium: GroupFields;
  minMonthsAfterStart: Field;
  maxGapMonths: Field;
  minTrafficPointB: Field;
  endVsPeakMinPct: Field;
}

const field = (value: number | null): Field => (value === null ? '' : value);

/** Группы в версии может не быть вовсе — тогда поля пусты, а не нулевые:
 *  ноль здесь означал бы «порог 0 %», то есть правило, пропускающее всех. */
const EMPTY_GROUP: GroupFields = {
  growthPctMin: '',
  growthAbsMin: '',
  growthPctMax: '',
  orHighPctLowAbs: false,
  supportingRequired: 0,
  refdomainsPctMin: '',
  kwTop10PctMin: '',
  minMonths: '',
};

/** Форма, заполненная значениями версии: правка всегда начинается с той,
 *  что действует, — пустая форма означала бы пороги, взятые из воздуха. */
export function valuesFrom(payload: Record<string, unknown>): FormValues {
  const rules = readRules(payload);
  const group = (source: typeof rules.good): GroupFields => {
    if (source === null) return EMPTY_GROUP;
    return {
      growthPctMin: field(source.growthPctMin),
      growthAbsMin: field(source.growthAbsMin),
      growthPctMax: field(source.growthPctMax),
      orHighPctLowAbs: source.orHighPctLowAbs,
      supportingRequired: source.supportingRequired ?? 0,
      refdomainsPctMin: field(source.refdomainsPctMin),
      kwTop10PctMin: field(source.kwTop10PctMin),
      minMonths: field(source.minMonths),
    };
  };

  return {
    version: '',
    note: '',
    good: group(rules.good),
    medium: group(rules.medium),
    minMonthsAfterStart: field(rules.minMonthsAfterStart),
    maxGapMonths: field(rules.maxGapMonths),
    minTrafficPointB: field(rules.minTrafficPointB),
    endVsPeakMinPct: field(rules.endVsPeakMinPct),
  };
}

const value = (field: Field): number | null => (field === '' ? null : field);

/** Пустое поле там, где сервер допускает «без границы» (`float | None`). */
const orNull = (field: Field): number | null => value(field);

/** Пустое поле там, где ноль и есть «выключено» (`float` с умолчанием 0).
 *  Отправить сюда `null` значит получить `422`: модель порогов не принимает
 *  отсутствие, она принимает ноль. */
const orZero = (field: Field): number => (field === '' ? 0 : field);

/**
 * Поля, которые сервер обязан получить числом: у них нет ни `None`, ни
 * умолчания, означающего «выключено». Пустыми их отправлять нельзя — вернётся
 * `422`, и человек узнает об этом уже после сохранения.
 */
export function missingRequired(values: FormValues): string[] {
  const empty: string[] = [];
  const group = (fields: GroupFields, title: string) => {
    if (fields.growthPctMin === '') empty.push(`${title}: рост трафика от, %`);
    if (fields.refdomainsPctMin === '') empty.push(`${title}: ссылающиеся домены от, %`);
    if (fields.kwTop10PctMin === '') empty.push(`${title}: ключи в топ-10 от, %`);
    if (fields.minMonths === '') empty.push(`${title}: не раньше, месяцев после старта`);
  };
  group(values.good, 'Хороший');
  group(values.medium, 'Средний');
  if (values.minMonthsAfterStart === '') empty.push('Пригодность: не раньше, месяцев после старта');
  if (values.maxGapMonths === '') empty.push('Пригодность: разрыв в рядах не больше, месяцев');
  return empty;
}

function applyGroup(target: Record<string, unknown>, fields: GroupFields): void {
  const traffic = target.org_traffic as Record<string, unknown>;
  traffic.growth_pct_min = value(fields.growthPctMin);
  // Эти два поля сервер объявляет как `float | None`: пусто здесь означает
  // «без нижней/верхней границы», а не ноль.
  traffic.growth_abs_min = orNull(fields.growthAbsMin);
  traffic.growth_pct_max = orNull(fields.growthPctMax);
  traffic.or_high_pct_low_abs = fields.orHighPctLowAbs;
  target.supporting_required = fields.supportingRequired;
  const supporting = target.supporting as Record<string, unknown>;
  supporting.refdomains_growth_pct_min = value(fields.refdomainsPctMin);
  supporting.kw_top10_growth_pct_min = value(fields.kwTop10PctMin);
  target.min_months_after_start = value(fields.minMonths);
}

/**
 * Значения формы поверх версии-основы.
 *
 * Копия глубокая: правка не должна менять ту версию, с которой начали, — она
 * уже утверждена, и вердикты на неё ссылаются.
 */
export function payloadFrom(
  base: Record<string, unknown>,
  values: FormValues,
): Record<string, unknown> {
  const payload = structuredClone(base);
  const groups = payload.groups as Record<string, Record<string, unknown>>;
  if (groups.good) applyGroup(groups.good, values.good);
  if (groups.medium) applyGroup(groups.medium, values.medium);

  const eligibility = payload.eligibility as Record<string, unknown>;
  eligibility.min_months_after_start = value(values.minMonthsAfterStart);
  eligibility.max_series_gap_months = value(values.maxGapMonths);
  // Ноль здесь — «условие выключено», и модель ждёт именно ноль, не отсутствие.
  eligibility.min_traffic_point_b = orZero(values.minTrafficPointB);

  const guards = payload.guards as Record<string, unknown>;
  guards.end_vs_peak_min_pct = orZero(values.endVsPeakMinPct);

  payload.version = values.version;
  return payload;
}
