import React, { useMemo, useState, useEffect } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type SearchItem = { id: string; title?: string; url?: string | null; score: number; snippet?: string };

export default function AIGuide(props: { apiBase?: string }) {
  const [mode, setMode] = useState<"search" | "ask">("search");
  const [q, setQ] = useState("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [apiOK, setApiOK] = useState<boolean | null>(null);

  const [results, setResults] = useState<SearchItem[]>([]);
  const [answer, setAnswer] = useState<string>("");
  const [citations, setCitations] = useState<Citation[]>([]);

  const apiBase = useMemo(() => {
    // Reihenfolge: Prop -> PUBLIC_API_BASE -> Hostname:9000 (lokal) -> Fallback 127.0.0.1
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore PUBLIC_ Variablen sind zur Buildzeit inline
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") {
      // Dev: localhost → 9000; Prod: gleiche Hostname:9000 (da Nginx statisch, API separat)
      return `${window.location.protocol}//${window.location.hostname}:9000`;
    }
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // API-Reachability anzeigen
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/ping`, { method: "GET" });
        if (!alive) return;
        setApiOK(r.ok);
      } catch {
        if (!alive) return;
        setApiOK(false);
      }
    })();
    return () => { alive = false };
  }, [apiBase]);

  async function doSearch() {
    setLoading(true); setErr(null); setResults([]);
    try {
      const url = `${apiBase}/v1/search?q=${encodeURIComponent(q)}&top_k=${k}`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = await r.json();
      setResults(data.results || []);
    } catch (e:any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function doAsk() {
    setLoading(true); setErr(null); setAnswer(""); setCitations([]);
    try {
      const r = await fetch(`${apiBase}/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, top_k: k }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);
      setAnswer(data.answer || "");
      setCitations(data.citations || []);
    } catch (e:any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "2rem auto", padding: "1rem" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>AI-Guide</h1>
      
      <div style={{ fontSize: 14, opacity: 0.8, marginBottom: "1rem", display:"flex", gap:8, alignItems:"center" }}>
        API: <code>{apiBase}</code>
        {apiOK === null ? <span>· prüfe…</span> :
        apiOK ? <span style={{color:"#0a7"}}>· verbunden</span> :
                <span style={{color:"#b00020"}}>· nicht erreichbar</span>}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={() => setMode("search")}
          style={{ padding: "6px 12px", borderRadius: 8, border: mode==="search" ? "2px solid #444" : "1px solid #ccc", background: "#fff", cursor:"pointer" }}
        >Search</button>
        <button
          onClick={() => setMode("ask")}
          style={{ padding: "6px 12px", borderRadius: 8, border: mode==="ask" ? "2px solid #444" : "1px solid #ccc", background: "#fff", cursor:"pointer" }}
        >Ask</button>
        <input
          type="number" min={1} max={10} value={k}
          onChange={(e)=>setK(Number(e.target.value))}
          style={{ marginLeft: "auto", width: 64, padding: "6px 8px", borderRadius: 8, border: "1px solid #ccc" }}
          title="top_k"
        />
      </div>

      <textarea
        value={q}
        onChange={(e)=>setQ(e.target.value)}
        placeholder={mode==="search" ? "Suche (z. B. nonuse loader)" : "Frage stellen…"}
        rows={4}
        style={{ width: "100%", padding: 12, borderRadius: 8, border: "1px solid #ccc", marginBottom: 12 }}
      />
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {mode==="search" ? (
          <button onClick={doSearch} disabled={loading || !q.trim()}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
            {loading ? "Suchen…" : "Search"}
          </button>
        ) : (
          <button onClick={doAsk} disabled={loading || !q.trim()}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
            {loading ? "Fragen…" : "Ask"}
          </button>
        )}
      </div>

      {err && <div style={{ color: "#b00020", marginBottom: 12 }}>⚠ {err}</div>}

      {mode==="search" && results.length>0 && (
        <div style={{ display: "grid", gap: 12 }}>
          {results.map((r)=>(
            <div key={String(r.id)} style={{ border: "1px solid #ddd", borderRadius: 10, padding: 12 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <strong>{r.title || "(ohne Titel)"}</strong>
                <span style={{ fontSize: 12, opacity: 0.7 }}>score {r.score.toFixed(3)}</span>
              </div>
              {r.url && <div style={{ fontSize: 13, marginTop: 4 }}><a href={r.url} target="_blank">{r.url}</a></div>}
              {r.snippet && <p style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{r.snippet}</p>}
            </div>
          ))}
        </div>
      )}

      {mode==="ask" && (answer || citations.length>0) && (
        <div style={{ display: "grid", gap: 12 }}>
          {answer && (
            <div style={{ border: "1px solid #ddd", borderRadius: 10, padding: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Antwort</div>
              <div style={{ whiteSpace: "pre-wrap" }}>{answer}</div>
            </div>
          )}
          {citations.length>0 && (
            <div style={{ border: "1px solid #eee", borderRadius: 10, padding: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Quellen</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {citations.map((c)=>(
                  <li key={c.id}>
                    {c.title || "(ohne Titel)"} {typeof c.score==="number" && <span style={{ opacity: .6 }}>· {c.score.toFixed(3)}</span>}
                    {c.url && <> – <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a></>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}