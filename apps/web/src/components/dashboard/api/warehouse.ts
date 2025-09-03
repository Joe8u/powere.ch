// apps/web/src/components/dashboard/api/warehouse.ts
import { API_BASE, fetchJson, toQuery } from './client';
import type { Agg, MfrrPoint, SurveyRow, LastprofileRow } from '../types';

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
  const raw = await fetchJson<any[]>(
    `/warehouse/regelenergie/tertiary${q}`,
    init
  );
  // Normalisiere 'timestamp' (raw) -> 'ts' (client-Format)
  return raw.map((r) => ({
    ts: r.ts ?? r.timestamp,
    total_called_mw: r.total_called_mw,
    avg_price_eur_mwh: r.avg_price_eur_mwh ?? null,
  })) as MfrrPoint[];
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
    `/warehouse/survey/wide${q}`,
    init
  );
}

// Lastprofile: /warehouse/lastprofile/series
export async function fetchLastprofile(
  opts?: {
    agg?: Agg;
    start?: string;
    end?: string;
    columns?: string; // Komma-Liste der Gruppen/Spalten
    limit?: number;
    offset?: number;
  },
  init?: RequestInit
): Promise<LastprofileRow[]> {
  const q = toQuery({
    agg: opts?.agg ?? 'hour',
    start: opts?.start,
    end: opts?.end,
    columns: opts?.columns,
    limit: opts?.limit ?? 24,
    offset: opts?.offset ?? 0,
  });
  return fetchJson<LastprofileRow[]>(
    `/warehouse/lastprofile/series${q}`,
    init
  );
}

export async function fetchLastprofileMeta(init?: RequestInit): Promise<{ columns: string[]; groups: string[] }> {
  return fetchJson<{ columns: string[]; groups: string[] }>(`/warehouse/lastprofile/columns`, init);
}

export async function fetchMfrrLatest(init?: RequestInit): Promise<string | null> {
  const r = await fetchJson<{ latest: string | null }>(`/warehouse/regelenergie/tertiary/latest_ts`, init);
  return r.latest ?? null;
}
