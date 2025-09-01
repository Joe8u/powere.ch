// apps/web/src/components/dashboard/hooks/useFetch.ts
import { useCallback, useEffect, useRef, useState } from 'react';

export type UseFetchResult<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

/**
 * Generischer Fetch-Hook mit Abort + manueller Neu­ladung.
 * @param fetcher  erhält ein AbortSignal und liefert Promise<T>
 * @param deps     Abhängig­keiten, bei deren Änderung neu geladen wird
 */
export function useFetch<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: any[] = []
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(() => {
    // alten Request abbrechen
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;

    setLoading(true);
    setError(null);

    fetcher(ctl.signal)
      .then((d) => {
        if (!ctl.signal.aborted) setData(d);
      })
      .catch((e) => {
        if (!ctl.signal.aborted) {
          const msg =
            e?.name === 'AbortError'
              ? 'Abgebrochen'
              : e?.message || 'Unbekannter Fehler';
          setError(msg);
        }
      })
      .finally(() => {
        if (!ctl.signal.aborted) setLoading(false);
      });
  // wichtig: fetcher UND deps in die Abhängigkeiten
  }, [fetcher, ...deps]);

  useEffect(() => {
    run();
    return () => abortRef.current?.abort();
  }, [run]);

  const refetch = useCallback(() => {
    run();
  }, [run]);

  return { data, loading, error, refetch };
}