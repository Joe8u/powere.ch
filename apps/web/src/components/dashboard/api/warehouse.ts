// apps/web/src/components/dashboard/api/warehouse.ts
import { fetchJson, toQuery } from './client';
import type { MfrrPoint, SurveyRow } from '../types';

export async function fetchMfrr(
  params: { agg?: 'raw' | 'hour' | 'day'; start?: string; end?: string; limit?: number; offset?: number } = {},
  init?: RequestInit & { timeoutMs?: number }
): Promise<MfrrPoint[]> {
  const { agg = 'hour', start, end, limit = 24, offset } = params;
  const q = toQuery({ agg, start, end, limit, offset });
  return fetchJson<MfrrPoint[]>(`/warehouse/regelenergie/tertiary${q}`, init);
}

export async function fetchSurvey(
  params: {
    columns?: string;
    respondent_id?: string;
    gender?: string;
    min_age?: number;
    max_age?: number;
    limit?: number;
    offset?: number;
  } = {},
  init?: RequestInit & { timeoutMs?: number }
): Promise<SurveyRow[]> {
  const {
    columns = 'respondent_id,age,gender',
    respondent_id,
    gender,
    min_age,
    max_age,
    limit = 5,
    offset,
  } = params;
  const q = toQuery({ columns, respondent_id, gender, min_age, max_age, limit, offset });
  return fetchJson<SurveyRow[]>(`/warehouse/survey/wide${q}`, init);
}