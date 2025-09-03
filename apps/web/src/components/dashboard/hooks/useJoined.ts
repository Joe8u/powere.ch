import { useCallback } from 'react';
import { useFetch } from './useFetch';
import { fetchJoined } from '../api/warehouse';
import type { LastprofileRow, Agg } from '../types';

export function useJoined(opts?: { agg?: Agg; start?: string; end?: string; columns?: string; limit?: number; offset?: number; }) {
  const cacheKey = `joined:${JSON.stringify(opts ?? {})}`;
  const fetcher = useCallback((signal: AbortSignal) => fetchJoined(opts, { signal }), [cacheKey]);
  return useFetch<LastprofileRow[]>(fetcher, [cacheKey], { cacheKey });
}

