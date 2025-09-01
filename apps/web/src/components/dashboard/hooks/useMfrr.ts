// apps/web/src/components/dashboard/hooks/useMfrr.ts
import { useFetch } from './useFetch';
import { fetchMfrr } from '../api/warehouse';
import type { MfrrPoint } from '../types';

export function useMfrr(params?: Parameters<typeof fetchMfrr>[0]) {
  return useFetch<MfrrPoint[]>(
    (signal) => fetchMfrr(params, { signal }),
    // deps: bei Objekt-Props JSON-stabilisieren
    [JSON.stringify(params ?? {})]
  );
}