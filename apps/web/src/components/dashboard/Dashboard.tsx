import { useEffect, useState } from "react";

type Healthz = {
  status: string;
  backend: string;
  dim: number;
  collection: string;
  chat_model: string | null;
};

type WarehousePing = { ok: boolean; root: string };

type SurveyRow = { respondent_id: string; age: number | null; gender: string | null };

type SearchHit = {
  id: string | number;
  title?: string | null;
  url?: string | null;
  score: number;
  snippet: string;
};

const API_BASE: string =
  (import.meta as any)?.env?.PUBLIC_API_BASE ?? "https://api.powere.ch";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Accept": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export default function Dashboard() {
  const [health, setHealth] = useState<Healthz | null>(null);
  const [wh, setWh] = useState<WarehousePing | null>(null);
  const [survey, setSurvey] = useState<SurveyRow[] | null>(null);
  const [search, setSearch] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [h, w, s, r] = await Promise.all([
          fetchJSON<Healthz>("/healthz"),
          fetchJSON<WarehousePing>("/warehouse/ping"),
          fetchJSON<SurveyRow[]>(
            "/warehouse/survey/wide?columns=respondent_id,age,gender&limit=3"
          ),
          fetchJSON<{ query: string; results: SearchHit[] }>(
            "/v1/search?q=test&top_k=3"
          ),
        ]);
        if (cancelled) return;
        setHealth(h);
        setWh(w);
        setSurvey(s);
        setSearch(r.results);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8">
      <div className="prose max-w-none">
        <h1 className="mb-2">powere.ch – Dashboard (Beta)</h1>
        <p className="mt-0">
          Kurzer Live-Check der Backend-Dienste und ein mini-Einblick in Daten.
          (Quelle: <code>{API_BASE}</code>)
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatusCard
          label="API Health"
          value={health ? "OK" : "…"}
          sub={
            health
              ? `${health.backend} · ${health.collection} · ${health.chat_model ?? "kein Chat"}`
              : "lädt…"
          }
          ok={!!health}
        />
        <StatusCard
          label="Warehouse"
          value={wh?.ok ? "OK" : "…"}
          sub={wh?.root ?? "lädt…"}
          ok={!!wh?.ok}
        />
        <StatusCard
          label="Survey (Rows)"
          value={survey ? `${survey.length}` : "…"}
          sub="limit=3"
          ok={!!survey}
        />
        <StatusCard
          label="RAG Treffer"
          value={search ? `${search.length}` : "…"}
          sub="q=test · top_k=3"
          ok={!!search}
        />
      </div>

      {/* Fehleranzeige */}
      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800">
          <strong>Fehler:</strong> {error}
        </div>
      )}

      {/* Tabellen */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Survey (Beispiel)</h2>
        <div className="overflow-x-auto rounded-lg border">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <Th>respondent_id</Th>
                <Th>age</Th>
                <Th>gender</Th>
              </tr>
            </thead>
            <tbody>
              {(survey ?? []).map((r) => (
                <tr key={r.respondent_id} className="odd:bg-white even:bg-gray-50">
                  <Td mono>{r.respondent_id}</Td>
                  <Td>{r.age ?? "—"}</Td>
                  <Td>{r.gender ?? "—"}</Td>
                </tr>
              ))}
              {(!survey || survey.length === 0) && (
                <tr>
                  <Td colSpan={3}>Keine Daten (oder lädt)…</Td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">RAG (Beispiele)</h2>
        <ul className="space-y-2">
          {(search ?? []).map((h) => (
            <li key={String(h.id)} className="rounded-lg border p-3">
              <div className="flex items-baseline justify-between gap-3">
                <div className="font-medium">{h.title ?? "Ohne Titel"}</div>
                <code className="text-xs">score: {h.score.toFixed(3)}</code>
              </div>
              {h.url && (
                <div className="text-xs text-blue-700 underline break-all">
                  <a href={h.url} target="_blank" rel="noreferrer">
                    {h.url}
                  </a>
                </div>
              )}
              <p className="mt-1 text-sm text-gray-700">
                {h.snippet?.trim() || "—"}
              </p>
            </li>
          ))}
          {(!search || search.length === 0) && <li>Keine Treffer (oder lädt)…</li>}
        </ul>
      </section>
    </div>
  );
}

function StatusCard(props: { label: string; value: string; sub?: string; ok?: boolean }) {
  return (
    <div className="rounded-2xl border p-4">
      <div className="text-sm text-gray-600">{props.label}</div>
      <div className="mt-1 text-2xl font-semibold">
        {props.value}
        <span
          className={`ml-2 inline-block h-2 w-2 rounded-full align-middle ${
            props.ok ? "bg-green-500" : "bg-gray-300"
          }`}
          title={props.ok ? "OK" : "unbekannt"}
        />
      </div>
      {props.sub && <div className="mt-1 text-xs text-gray-500">{props.sub}</div>}
    </div>
  );
}

function Th({ children }: { children: any }) {
  return <th className="px-3 py-2 text-left font-semibold text-gray-800">{children}</th>;
}
function Td({
  children,
  colSpan,
  mono,
}: {
  children: any;
  colSpan?: number;
  mono?: boolean;
}) {
  return (
    <td
      colSpan={colSpan}
      className={`px-3 py-2 ${mono ? "font-mono text-xs" : ""}`}
    >
      {children}
    </td>
  );
}