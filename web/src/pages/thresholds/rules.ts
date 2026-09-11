/**
 * Пороги словами: `Ruleset.payload` → подписи, понятные без JSON.
 *
 * Утверждают пороги Head of Link Building и Owner, а не инженер. Цифра,
 * показанная как `groups.good.org_traffic.growth_pct_min`, утверждается вслепую:
 * человек видит число, но не видит, что оно включает — и именно так граница
 * группы сдвигается «на глаз».
 *
 * Перевод живёт в одном месте, потому что подписи обязаны совпадать с теми, что
 * сервис уже говорит на карточке проекта («рост ссылающихся доменов», «рост
 * числа ключей в топ-10» — `classify/rules.py`). Разойдясь, они назвали бы одно
 * и то же разными словами на соседних экранах.
 */

/** Условие одной группы. `null` — условие не задано, и это не ноль. */
export interface GroupRule {
  growthPctMin: number | null;
  growthAbsMin: number | null;
  growthPctMax: number | null;
  orHighPctLowAbs: boolean;
  supportingRequired: number | null;
  refdomainsPctMin: number | null;
  kwTop10PctMin: number | null;
  minMonths: number | null;
}

export interface Rules {
  good: GroupRule | null;
  medium: GroupRule | null;
  minMonthsAfterStart: number | null;
  maxGapMonths: number | null;
  minTrafficPointB: number | null;
  endVsPeakMinPct: number | null;
  pointAMonths: number | null;
  pointBMonths: number | null;
  baseline: string | null;
  preStartMonths: number | null;
  normalizeAfterMonths: number | null;
}

function at(source: unknown, path: readonly string[]): unknown {
  let current = source;
  for (const key of path) {
    if (typeof current !== 'object' || current === null) return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

/** Число или `null`. Строку-число не принимаем: пороги приходят разобранными
 *  сервером, и «почти число» здесь означало бы чужую форму, а не опечатку. */
function num(source: unknown, ...path: string[]): number | null {
  const value = at(source, path);
  return typeof value === 'number' ? value : null;
}

function bool(source: unknown, ...path: string[]): boolean {
  return at(source, path) === true;
}

function text(source: unknown, ...path: string[]): string | null {
  const value = at(source, path);
  return typeof value === 'string' ? value : null;
}

function group(payload: unknown, name: string): GroupRule | null {
  if (at(payload, ['groups', name]) === undefined) return null;
  return {
    growthPctMin: num(payload, 'groups', name, 'org_traffic', 'growth_pct_min'),
    growthAbsMin: num(payload, 'groups', name, 'org_traffic', 'growth_abs_min'),
    growthPctMax: num(payload, 'groups', name, 'org_traffic', 'growth_pct_max'),
    orHighPctLowAbs: bool(payload, 'groups', name, 'org_traffic', 'or_high_pct_low_abs'),
    supportingRequired: num(payload, 'groups', name, 'supporting_required'),
    refdomainsPctMin: num(payload, 'groups', name, 'supporting', 'refdomains_growth_pct_min'),
    kwTop10PctMin: num(payload, 'groups', name, 'supporting', 'kw_top10_growth_pct_min'),
    minMonths: num(payload, 'groups', name, 'min_months_after_start'),
  };
}

export function readRules(payload: Record<string, unknown>): Rules {
  return {
    good: group(payload, 'good'),
    medium: group(payload, 'medium'),
    minMonthsAfterStart: num(payload, 'eligibility', 'min_months_after_start'),
    maxGapMonths: num(payload, 'eligibility', 'max_series_gap_months'),
    minTrafficPointB: num(payload, 'eligibility', 'min_traffic_point_b'),
    endVsPeakMinPct: num(payload, 'guards', 'end_vs_peak_min_pct'),
    pointAMonths: num(payload, 'windows', 'point_a_months'),
    pointBMonths: num(payload, 'windows', 'point_b_months'),
    baseline: text(payload, 'windows', 'baseline'),
    preStartMonths: num(payload, 'windows', 'pre_start_baseline_months'),
    normalizeAfterMonths: num(payload, 'duration', 'normalize_after_months'),
  };
}

/** База отсчёта словами: `period` и `pre_start` — внутренние значения, и на
 *  экране они ничего не объясняют человеку, который утверждает пороги. */
export function baselineWords(baseline: string | null): string {
  if (baseline === null) return '—';
  const known: Record<string, string> = {
    period: 'период работ',
    pre_start: 'месяцы до старта работ',
  };
  // Незнакомое значение показываем как есть: подменять его словом «период»
  // значило бы соврать про версию, которую кто-то завёл руками.
  return known[baseline] ?? baseline;
}

const pct = (value: number) => `${value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`;
const visits = (value: number) =>
  `${value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} визитов`;

/** Условие по трафику: главная метрика, с неё начинается проверка. */
function trafficLines(rule: GroupRule): string[] {
  const lines: string[] = [];

  if (rule.growthPctMin !== null && rule.growthPctMax !== null) {
    lines.push(`Рост трафика от ${pct(rule.growthPctMin)} до ${pct(rule.growthPctMax)}`);
  } else if (rule.growthPctMin !== null) {
    lines.push(`Рост трафика от ${pct(rule.growthPctMin)}`);
  }

  if (rule.growthAbsMin !== null) {
    lines.push(`И при этом прирост не меньше ${visits(rule.growthAbsMin)}`);
  }

  if (rule.orHighPctLowAbs) {
    // Вилка Приложения А: без неё «средних» читают как «просто слабее», а туда
    // попадает и сильный процент с маленьким абсолютным приростом.
    lines.push('Сюда же попадает сильный рост в процентах при малом приросте в визитах');
  }

  return lines;
}

/** Подтверждающие метрики: сколько их нужно и какие ориентиры. */
function supportingLines(rule: GroupRule): string[] {
  if (rule.supportingRequired === null || rule.refdomainsPctMin === null) return [];
  if (rule.kwTop10PctMin === null) return [];

  const ориентиры = `ссылающиеся домены от ${pct(rule.refdomainsPctMin)}, ключи в топ-10 от ${pct(rule.kwTop10PctMin)}`;
  return [
    rule.supportingRequired > 0
      ? `Подтверждающих метрик нужно ${rule.supportingRequired} из 2: ${ориентиры}`
      : `Подтверждающие метрики не требуются (ориентиры: ${ориентиры})`,
  ];
}

/** Условия группы предложениями. Порядок — тот, в котором их проверяет сервис. */
export function groupSentences(rule: GroupRule): string[] {
  const months =
    rule.minMonths === null ? [] : [`Не раньше ${rule.minMonths} месяцев после старта работ`];
  return [...trafficLines(rule), ...supportingLines(rule), ...months];
}
