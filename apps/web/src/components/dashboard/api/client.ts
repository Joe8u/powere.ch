// apps/web/src/components/dashboard/api/client.ts
/**
 * Zentraler API-Client + kleine Helpers.
 * - PUBLIC_API_BASE aus .env(.local) wenn gesetzt
 * - sonst: lokal -> 127.0.0.1:9000, prod -> api.powere.ch
 */
export const API_BASE: string = (() => {
  const envBase = (import.meta as any).env?.PUBLIC_API_BASE as string | undefined;
  if (envBase && envBase.trim()) return envBase.trim();

  if (typeof window !== 'undefined') {
    const h = window.location.hostname;
    if (h === 'localhost' || h === '127.0.0.1') return 'http://127.0.0.1:9000';
  }
  return 'https://api.powere.ch';
})();

export function toQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    sp.append(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), init?.timeoutMs ?? 15000);

  try {
    const res = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status} ${res.statusText} – ${text || 'request failed'}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}