// apps/web/src/components/dashboard/hooks/useFetch.ts
import { useCallback, useEffect, useRef, useState } from 'react';

export type UseFetchResult<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

type Options = {
  /** eindeutiger Key für Cache (z.B. 'mfrr:{"agg":"hour"}') */
  cacheKey?: string;
  /** wie lange Cache als „frisch“ gilt (nur Info; wir revalidieren eh) */
  staleMs?: number;
};

export function useFetch<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: any[] = [],
  options?: Options
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(deps);
  const ctrlRef = useRef<AbortController | null>(null);
  const fnRef = useRef(fn);
  // Halte stets die neueste fn-Referenz, aber entkopple run von Render-Zyklen
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  const run = useCallback((showLoading: boolean) => {
    if (ctrlRef.current) ctrlRef.current.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;

    if (showLoading) setLoading(true);
    setError(null);

    return fnRef.current(ctrl.signal)
      .then((res) => {
        setData(res);
        if (options?.cacheKey) {
          try {
            sessionStorage.setItem(
              options.cacheKey,
              JSON.stringify({ ts: Date.now(), data: res })
            );
          } catch {}
        }
      })
      .catch((e: any) => {
        if (e?.name !== 'AbortError') setError(e?.message ?? 'Unbekannter Fehler');
      })
      .finally(() => setLoading(false));
  }, [options?.cacheKey]);

  useEffect(() => {
    let hadCache = false;
    if (options?.cacheKey) {
      try {
        const raw = sessionStorage.getItem(options.cacheKey);
        if (raw) {
          const cached = JSON.parse(raw);
          setData(cached.data as T);
          setLoading(false);      // keine Lade-UI zeigen
          hadCache = true;
        }
      } catch {}
    }
    run(!hadCache);               // mit Cache: ohne Loading, sonst mit Loading

    return () => {
      if (ctrlRef.current) ctrlRef.current.abort();
    };
  }, [key, run, options?.cacheKey]);

  const refetch = useCallback(() => {
    run(false);                   // revalidate ohne Loading-Flicker
  }, [run]);

  return { data, loading, error, refetch };
}
