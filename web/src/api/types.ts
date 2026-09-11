/** Формы ответов API. Ровно то, что рисуют экраны. */

export interface WhoAmI {
  email: string;
  full_name: string;
  group: string;
  rights: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_hours: number;
  group: string;
  rights: string[];
}

export interface RejectionRow {
  row_no: number;
  field: string;
  reason: string;
  detail: string;
}

export interface IntakeReport {
  origin: string;
  accepted: number;
  created: number;
  updated: number;
  rejected_rows: number;
  by_reason: Record<string, number>;
  rejections: RejectionRow[];
  /** Непонятые ячейки **принятых** строк: проект в сервисе есть, цифру можно
   *  уточнить позже. В число отклонённых строк они не входят. */
  notices: RejectionRow[];
}

export interface RunEstimate {
  projects: number;
  units_estimated: number;
  requests_planned: number;
  requests_cached: number;
  scheme_lines: string[];
  quota_left: number | null;
  quota_reserved: number;
  /** `ok` | `not_enough` | `unknown` — три разных действия человека. */
  verdict: string;
  may_start: boolean;
  reason: string;
}

export interface RunStarted {
  run_id: number;
  queued_as: string;
}

export interface RunRow {
  id: number;
  status: string;
  started_by: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  projects_total: number;
  projects_ok: number;
  projects_failed: number;
  units_estimated: number;
  units_actual: number;
  error: string;
}

export interface ProjectRow {
  id: number;
  domain: string;
  niche: string;
  geo: string;
  service_type: string;
  period_start: string;
  period_end: string;
  publishable: boolean;
  status: string;
  /** `null` — проект не классифицирован действующей версией порогов. Это
   *  ответ, а не пустота: докупить историю и запустить классификацию. */
  group: string | null;
  score: number | null;
}

export interface ProjectsQuery {
  group?: string | null;
  query?: string;
  limit: number;
  offset: number;
}

export interface ComparisonRow {
  subject: string;
  label: string;
  before: number;
  after: number;
  absolute: number;
  /** `null` — рост от нулевой базы: процента у него нет. */
  pct: number | null;
}

export interface ReasonRow {
  subject: string;
  fact: number | null;
  threshold: number | null;
  passed: boolean;
  decisive: boolean;
  note: string;
}

export interface VerdictView {
  group: string;
  score: number;
  ruleset_version: string;
  decided_at: string;
  reasons: ReasonRow[];
  point_a: Record<string, number>;
  point_b: Record<string, number>;
  comparison: ComparisonRow[];
}

export interface SeriesRow {
  metric: string;
  points: [string, number][];
}

export interface ProjectCard {
  project: ProjectRow;
  verdict: VerdictView | null;
  series: SeriesRow[];
}

export interface ChartBlock {
  title: string;
  svg: string;
}

export interface CaseRow {
  id: number;
  project_id: number;
  domain: string;
  version: number;
  /** Кейс собран без имени домена: публиковать его под именем нельзя. */
  anonymized: boolean;
  status: string;
  created_at: string;
  /** `null` — кейс в базе есть, файла к нему нет: скачивать нечего. */
  filename: string | null;
  checksum: string | null;
}

export interface PackView {
  exists: boolean;
  filename: string | null;
  size_bytes: number | null;
  built_at: string | null;
  /** Что сказать человеку: когда пачка собрана или почему её нет. */
  note: string;
}

export interface UsageView {
  spent: number;
  reserved: number;
  /** `null` — остаток не узнали. Это не ноль: ноль означал бы «квота кончилась». */
  remaining: number | null;
  per_hundred_domains: number | null;
}

export interface RulesetRow {
  id: number;
  version: string;
  is_active: boolean;
  note: string;
  created_at: string;
  /** Пороги целиком. Форму знает `pages/thresholds/rules.ts` — там же и разбор. */
  payload: Record<string, unknown>;
}

export interface PreviewChange {
  domain: string;
  /** `null` — вердикта ещё не было: проект получит группу впервые. */
  was: string | null;
  becomes: string;
}

export interface PreviewView {
  version: string;
  total: number;
  changes: PreviewChange[];
  first_time: PreviewChange[];
  unchanged: number;
  /** Проекты, которые этой версией считать нечем: не куплены нужные месяцы.
   *  Это третье состояние, а не разновидность «не изменится». */
  missing_data: string[];
}

export interface RecalcView {
  version: string;
  /** Отчёт пересчёта строками — тот же, что печатает консольная команда. */
  lines: string[];
}

export interface AlertView {
  kind: string;
  /** `critical` | `serious` | `warning` | `good` — четыре, а не две. */
  severity: string;
  message: string;
}
