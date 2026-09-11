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
  projects_total: number;
  projects_ok: number;
  projects_failed: number;
  units_estimated: number;
  units_actual: number;
  error: string;
}
