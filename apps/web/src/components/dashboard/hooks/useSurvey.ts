// apps/web/src/components/dashboard/hooks/useSurvey.ts
import { useFetch } from './useFetch';
import { fetchSurvey } from '../api/warehouse';
import type { SurveyRow } from '../types';

export function useSurvey(params?: Parameters<typeof fetchSurvey>[0]) {
  return useFetch<SurveyRow[]>(
    (signal) => fetchSurvey(params, { signal }),
    [JSON.stringify(params ?? {})]
  );
}