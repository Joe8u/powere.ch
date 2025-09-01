// apps/web/src/components/dashboard/hooks/useSurvey.ts
import { useFetch, type UseFetchResult } from './useFetch';
import { fetchSurvey } from '../api/warehouse';
import type { SurveyRow } from '../types';

export function useSurvey(
  params?: Parameters<typeof fetchSurvey>[0]
): UseFetchResult<SurveyRow[]> {
  return useFetch<SurveyRow[]>(
    (signal) => fetchSurvey(params, { signal }),
    [JSON.stringify(params ?? {})]
  );
}