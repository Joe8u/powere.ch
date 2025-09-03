// apps/web/src/components/dashboard/hooks/useSurvey.ts
import { useCallback } from 'react';
import { useFetch } from './useFetch';
import { fetchSurvey } from '../api/warehouse';
import type { SurveyRow } from '../types';

export function useSurvey(params?: Parameters<typeof fetchSurvey>[0]) {
  const cacheKey = `survey:${JSON.stringify(params ?? {})}`;
  const fetcher = useCallback((signal: AbortSignal) => fetchSurvey(params, { signal }), [cacheKey]);
  return useFetch<SurveyRow[]>(fetcher, [cacheKey], { cacheKey });
}
