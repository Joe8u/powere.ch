import { useFetch, type UseFetchResult } from './useFetch';
import { fetchMfrr } from '../api/warehouse';
import type { MfrrPoint, Agg } from '../types';

export function useMfrr(opts?: {
  agg?: Agg;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}): UseFetchResult<MfrrPoint[]> {
  return useFetch<MfrrPoint[]>(
    (signal) => fetchMfrr(opts, { signal }),
    [JSON.stringify(opts ?? {})]
  );
}