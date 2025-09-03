import { useCallback, useEffect, useState } from 'react';
import { fetchLastprofile, fetchLastprofileMeta } from '../api/warehouse';
import type { Agg, LastprofileRow } from '../types';

export function useLastprofile(opts?: { agg?: Agg; columns?: string; start?: string; end?: string; limit?: number; offset?: number }) {
  const cacheKey = `lp:${JSON.stringify(opts ?? {})}`;
  const [rows, setRows] = useState<LastprofileRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLastprofile(opts);
      setRows(data);
    } catch (e: any) {
      setError(e?.message ?? 'Unbekannter Fehler');
    } finally {
      setLoading(false);
    }
  }, [cacheKey]);

  useEffect(() => { run(); }, [run]);

  return { rows, loading, error, refetch: run };
}

export function useLastprofileGroups() {
  const [groups, setGroups] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const meta = await fetchLastprofileMeta();
        if (!alive) return;
        setGroups(meta.groups || []);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message ?? 'Unbekannter Fehler');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false };
  }, []);

  return { groups, loading, error };
}

