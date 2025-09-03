import { useCallback } from 'react';
import { useFetch } from './useFetch';
import { fetchMfrr } from '../api/warehouse';
import type { MfrrPoint, Agg } from '../types';

export function useMfrr(opts?: {
  agg?: Agg; start?: string; end?: string; limit?: number; offset?: number;
}) {
  const cacheKey = `mfrr:${JSON.stringify(opts ?? {})}`;
  const fetcher = useCallback((signal: AbortSignal) => fetchMfrr(opts, { signal }), [cacheKey]);
  return useFetch<MfrrPoint[]>(fetcher, [cacheKey], { cacheKey });
}
