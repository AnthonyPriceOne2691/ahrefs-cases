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
