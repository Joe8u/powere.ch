// apps/web/src/components/dashboard/hooks/useFetch.ts
import { useEffect, useState } from 'react';

export function useFetch<T>(
  factory: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = []
): { data: T | null; loading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);

    factory(ac.signal)
      .then((d) => setData(d))
      .catch((e) => {
        if ((e && e.name) === 'AbortError') return;
        setError(e?.message || 'Unbekannter Fehler');
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });

    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}