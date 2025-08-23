import React, { useMemo, useState, useEffect } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type SearchItem = { id: string; title?: string; url?: string | null; score: number; snippet?: string };

type Meta = {
  top_k: number;
  timing_ms: { embedding: number; search: number; llm: number; total: number };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  messages_preview?: { user?: string };
};

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
  const [meta, setMeta] = useState<Meta | null>(null);
  const [debug, setDebug] = useState(false);

  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore – zur Buildzeit inline
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") {
      return `${window.location.protocol}//${window.location.hostname}:9000`;
    }
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // API-Reachability
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

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 12px",
    borderRadius: 8,
    border: active ? "1px solid #111" : "1px solid #ccc",
    background: active ? "#111" : "#fff",
    color: active ? "#fff" : "#111",
    cursor: "pointer",
  });

  async function doSearch() {
    setLoading(true); setErr(null); setResults([]); setAnswer(""); setCitations([]); setMeta(null);
    try {
      const url = `${apiBase}/v1/search?q=${encodeURIComponent(q)}&top_k=${k}`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = await r.json();
      setResults(data.results || []);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function doAsk() {
    setLoading(true); setErr(null); setAnswer(""); setCitations([]); setMeta(null);
    try {
      const url = `${apiBase}/v1/chat${debug ? "?debug=1" : ""}`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, top_k: k }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);
      setAnswer(data.answer || "");
      setCitations(data.citations || []);
      if (debug && data.meta) setMeta(data.meta as Meta);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function copyMeta() {
    if (!meta) return;
    const raw = JSON.stringify(meta, null, 2);
    navigator.clipboard?.writeText(raw).catch(() => {});
  }

  return (
    <div style={{ maxWidth: 900, margin: "2rem auto", padding: "1rem" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>AI-Guide</h1>

      <div style={{ fontSize: 14, opacity: 0.9, marginBottom: "1rem", display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
        API: <code>{apiBase}</code>
        {apiOK === null ? <span>· prüfe…</span> :
         apiOK ? <span style={{color:"#0a7"}}>· verbunden</span> :
                 <span style={{color:"#b00020"}}>· nicht erreichbar</span>}
        <label style={{ marginLeft: "auto", display:"flex", alignItems:"center", gap:6 }}>
          <input type="checkbox" checked={debug} onChange={(e)=>setDebug(e.target.checked)} />
          <span style={{ fontSize: 13 }}>Debug</span>
        </label>
        <input
          type="number" min={1} max={10} value={k}
          onChange={(e)=>setK(Number(e.target.value))}
          style={{ width: 64, padding: "6px 8px", borderRadius: 8, border: "1px solid #ccc" }}
          title="top_k"
        />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button onClick={() => setMode("search")} style={tabStyle(mode==="search")}>Search</button>
        <button onClick={() => setMode("ask")} style={tabStyle(mode==="ask")}>Ask</button>
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
          <button onClick={doSearch} disabled={loading || !q.trim() || apiOK === false}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
            {loading ? "Suchen…" : "Search"}
          </button>
        ) : (
          <button onClick={doAsk} disabled={loading || !q.trim() || apiOK === false}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
            {loading ? "Fragen…" : "Ask"}
          </button>
        )}
      </div>

      {err && <div style={{ color: "#b00020", marginBottom: 12 }}>⚠ {err}</div>}

      {/* SEARCH MODE RESULTS */}
      {mode==="search" && results.length>0 && (
        <div style={{ display: "grid", gap: 12 }}>
          {results.map((r)=>(
            <div key={String(r.id)} style={{ border: "1px solid #ddd", borderRadius: 10, padding: 12 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap:"wrap" }}>
                <strong>{r.title || "(ohne Titel)"}</strong>
                <span style={{ fontSize: 12, opacity: 0.7 }}>score {r.score.toFixed(3)}</span>
              </div>
              {r.url && <div style={{ fontSize: 13, marginTop: 4 }}>
                <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a>
              </div>}
              {r.snippet && <p style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{r.snippet}</p>}
            </div>
          ))}
        </div>
      )}

      {/* ASK MODE ANSWER + DEBUG */}
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

          {/* Debug-Panel */}
          {debug && meta && (
            <div style={{ border: "1px dashed #bbb", borderRadius: 10, padding: 12, background:"#fafafa" }}>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <strong>Debug</strong>
                <span style={{ fontSize: 12, opacity:.7 }}>top_k {meta.top_k}</span>
                <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
                  <button onClick={copyMeta} style={{ fontSize:12, padding:"4px 8px", border:"1px solid #ccc", borderRadius:8, background:"#fff", cursor:"pointer" }}>
                    Copy meta
                  </button>
                  <details>
                    <summary style={{ cursor:"pointer", fontSize:12 }}>Raw JSON</summary>
                    <pre style={{ marginTop:8, maxHeight:240, overflow:"auto" }}>
{JSON.stringify(meta, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>

              <div style={{ marginTop:10, display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))", gap:8 }}>
                <div style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"8px 10px" }}>
                  <div style={{ fontSize:12, opacity:.7 }}>Embedding</div>
                  <div style={{ fontWeight:600 }}>{meta.timing_ms.embedding} ms</div>
                </div>
                <div style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"8px 10px" }}>
                  <div style={{ fontSize:12, opacity:.7 }}>Search</div>
                  <div style={{ fontWeight:600 }}>{meta.timing_ms.search} ms</div>
                </div>
                <div style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"8px 10px" }}>
                  <div style={{ fontSize:12, opacity:.7 }}>LLM</div>
                  <div style={{ fontWeight:600 }}>{meta.timing_ms.llm} ms</div>
                </div>
                <div style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"8px 10px" }}>
                  <div style={{ fontSize:12, opacity:.7 }}>Total</div>
                  <div style={{ fontWeight:600 }}>{meta.timing_ms.total} ms</div>
                </div>
              </div>

              <div style={{ marginTop:10, display:"flex", gap:8, flexWrap:"wrap" }}>
                <span style={{ fontSize:12, border:"1px solid #ddd", borderRadius:16, padding:"4px 10px", background:"#fff" }}>
                  Collection: <strong>{meta.backend.collection}</strong>
                </span>
                <span style={{ fontSize:12, border:"1px solid #ddd", borderRadius:16, padding:"4px 10px", background:"#fff" }}>
                  Embed: <strong>{meta.backend.embed_backend}</strong>
                </span>
                <span style={{ fontSize:12, border:"1px solid #ddd", borderRadius:16, padding:"4px 10px", background:"#fff" }}>
                  Model: <strong>{meta.backend.chat_model}</strong>
                </span>
                {meta.token_usage && (
                  <span style={{ fontSize:12, border:"1px solid #ddd", borderRadius:16, padding:"4px 10px", background:"#fff" }}>
                    Tokens: <strong>{meta.token_usage.total_tokens ?? "-"}</strong>
                  </span>
                )}
              </div>

              <div style={{ marginTop:12 }}>
                <div style={{ fontWeight:600, marginBottom:6 }}>Retrieval</div>
                <div style={{ display:"grid", gap:8 }}>
                  {meta.retrieval.map((r)=>(
                    <div key={`${r.rank}-${r.id}`} style={{ border:"1px solid #eee", borderRadius:8, padding:10 }}>
                      <div style={{ display:"flex", gap:8, alignItems:"baseline", flexWrap:"wrap" }}>
                        <span style={{ fontSize:12, opacity:.7 }}>#{r.rank}</span>
                        <strong>{r.title || "(ohne Titel)"}</strong>
                        {typeof r.score === "number" && <span style={{ fontSize:12, opacity:.7 }}>score {r.score.toFixed(3)}</span>}
                      </div>
                      <div style={{ fontSize:12, opacity:.75, marginTop:4, wordBreak:"break-all" }}>
                        id {r.id}{r.url ? <> · <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a></> : null}
                      </div>
                      {r.snippet && <div style={{ marginTop:8, whiteSpace:"pre-wrap", fontSize:13 }}>{r.snippet}</div>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}