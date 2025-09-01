// apps/web/src/components/dashboard/api/warehouse.ts
import { API_BASE, fetchJson, toQuery } from './client';
import type { Agg, MfrrPoint, SurveyRow } from '../types';

// mFRR: /warehouse/regelenergie/tertiary
export async function fetchMfrr(
  opts?: {
    agg?: Agg;
    start?: string;
    end?: string;
    limit?: number;
    offset?: number;
  },
  init?: RequestInit
): Promise<MfrrPoint[]> {
  const q = toQuery({
    agg: opts?.agg ?? 'hour',
    start: opts?.start,
    end: opts?.end,
    limit: opts?.limit ?? 24,
    offset: opts?.offset ?? 0,
  });
  return fetchJson<MfrrPoint[]>(
    `${API_BASE}/warehouse/regelenergie/tertiary?${q}`,
    init
  );
}

// Survey: /warehouse/survey/wide
export async function fetchSurvey(
  params?: {
    columns?: string;
    respondent_id?: string;
    gender?: string;
    min_age?: number;
    max_age?: number;
    limit?: number;
    offset?: number;
  },
  init?: RequestInit
): Promise<SurveyRow[]> {
  const q = toQuery({
    columns: params?.columns,
    respondent_id: params?.respondent_id,
    gender: params?.gender,
    min_age: params?.min_age,
    max_age: params?.max_age,
    limit: params?.limit ?? 5,
    offset: params?.offset ?? 0,
  });
  return fetchJson<SurveyRow[]>(
    `${API_BASE}/warehouse/survey/wide?${q}`,
    init
  );
}