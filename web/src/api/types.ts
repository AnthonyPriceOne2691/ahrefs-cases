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

/** Кем запускались прогоны — вариант отбора журнала. */
export interface RunAuthor {
  id: number;
  name: string;
  deleted: boolean;
}

export interface RunRow {
  id: number;
  status: string;
  started_by: number;
  /** Кто запустил — именем. Пусто, если учётки уже нет вовсе. */
  started_by_name: string;
  /** Учётку автора удалили: в журнале он остаётся с пометкой «(удалён)». */
  started_by_deleted: boolean;
  /** `stage1` | `stage2` | `case_data` | `cases`; пусто — прогон старше поля. */
  stage: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  projects_total: number;
  projects_ok: number;
  projects_failed: number;
  /** Проекты, по которым данных не появилось: ни собраны, ни упали. */
  projects_skipped: number;
  units_estimated: number;
  units_actual: number;
  error: string;
}

/** Судьба одного проекта в прогоне: что с ним стало и почему. */
export interface RunItemView {
  domain: string;
  outcome: string;
  reason: string;
  units_actual: number;
  /** Проект с тех пор удалён: строка журнала осталась, ссылки на проект нет. */
  project_deleted?: boolean;
}

/** Прогон со списком судеб — то, что открывают, когда «17 из 19» мало. */
export interface RunCard extends RunRow {
  fates: RunItemView[];
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
  /**
   * Почему факта нет, если его нет.
   *
   * `not_bought` — историю метрики не покупали (шаг 2 платится только
   * кандидатам в кейсы), `no_data` — купили, а Ahrefs ничего не отдал.
   * `null` — сказать нечего: либо факт есть, либо условие не про метрику,
   * либо журнал расхода про этот домен молчит.
   */
  fact_missing?: 'not_bought' | 'no_data' | null;
}

export interface VerdictView {
  group: string;
  /**
   * Почему «стало» в таблице и конец кривой — разные числа.
   *
   * Приходит с сервера: та же строка печатается в PDF, и вторая копия на
   * фронте разошлась бы с первой (Z32).
   */
  points_note?: string;
  score: number;
  ruleset_version: string;
  decided_at: string;
  reasons: ReasonRow[];
  point_a: Record<string, number>;
  point_b: Record<string, number>;
  comparison: ComparisonRow[];
  /** По каким рядам посчитан вердикт. `null` — вынесен до того, как источник стали записывать. */
  source: string | null;
}

export interface SeriesRow {
  metric: string;
  points: [string, number][];
}

export interface ProjectCard {
  project: ProjectRow;
  verdict: VerdictView | null;
  series: SeriesRow[];
  series_source: string;
  /**
   * Числа вердикта посчитаны не по тем рядам, которые показаны рядом.
   * Решает сервер: правило одно на лист PDF и на карточку (Z10).
   */
  source_mismatch: string | null;
}

/**
 * Что удаление проекта уносит и что оставляет. Одна форма на предпросмотр
 * (`GET …/deletion`) и на ответ удаления — числа считает сервер (урок L78).
 */
export interface ProjectDeletion {
  project_id: number;
  domain: string;
  metric_points: number;
  verdicts: number;
  cases: number;
  /** PDF, уходящие с диска: общий с кейсом другого проекта файл остаётся. */
  files: number;
  /** Строки журнала прогонов — остаются, домен в них подписан удалённым. */
  run_items: number;
  /** Другие кампании того же сайта: их данные — свои копии, они остаются. */
  twin_campaigns: number;
  /** Свежая пачка содержит кейс проекта и после удаления не скачается. */
  pack_blocked: boolean;
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
  /** Группа, которой файл собран, и группа проекта сейчас. */
  case_group?: string | null;
  current_group?: string | null;
  /**
   * Почему файл больше не объясняет сегодняшнюю группу (Z30).
   *
   * `group` — проекту кейс больше не положен, `verdict` — файл собран другим
   * расчётом, `numbers` — расчёт тот же, а числа в файле другие (вердикт
   * пересчитан поверх), `gone` — действующего вердикта нет. `null`/отсутствие —
   * файл и экран об одном.
   */
  outdated?: 'group' | 'verdict' | 'numbers' | 'gone' | null;
}

export interface PackView {
  exists: boolean;
  filename: string | null;
  size_bytes: number | null;
  built_at: string | null;
  /** Что сказать человеку: когда пачка собрана, почему её нет или не отдаём. */
  note: string;
  /** Почему пачку не отдают: в ней кейс удалённого проекта. Лечит пересборка. */
  outdated?: 'project_deleted' | null;
}

export interface UsageView {
  /** Настоящий расход — только живые прогоны. */
  spent: number;
  /** Условные units прогонов без живого ключа: столько стоили бы они вживую. Не расход. */
  conditional: number;
  reserved: number;
  /** `null` — остаток не узнали. Это не ноль: ноль означал бы «квота кончилась». */
  remaining: number | null;
  /** Расход, которого счётчик Ahrefs ещё не увидел: прогон считается по разнице. */
  uncounted: number;
  /** Сколько доменов оплачено живьём — знаменатель стоимости на сто доменов. */
  live_domains: number;
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

export interface UserRow {
  id: number;
  email: string;
  full_name: string;
  group: string;
  is_active: boolean;
  /** Решённое **лично**: `true` — выдано сверх группы, `false` — отобрано у неё. */
  personal_rights: Record<string, boolean>;
  /** Итог: что человеку можно на самом деле. */
  rights: string[];
}

export interface UserWithPassword {
  user: UserRow;
  /** Показывается **один раз**: в базе только хеш, повторно — перевыпуск. */
  password: string;
}

export interface UserPatch {
  group?: string;
  is_active?: boolean;
  full_name?: string;
  /** Личные права целиком: `true` выдаёт сверх группы, `false` отбирает,
   *  отсутствие ключа — «как в группе». */
  personal_rights?: Record<string, boolean>;
}

export interface RightsCatalog {
  rights: string[];
  /** Что даёт каждая группа. По этому списку экран отличает право «как в
   *  группе» от выданного лично, не храня второй копии таблицы прав. */
  groups: Record<string, string[]>;
}

export interface AlertView {
  kind: string;
  /** `critical` | `serious` | `warning` | `good` — четыре, а не две. */
  severity: string;
  message: string;
}
