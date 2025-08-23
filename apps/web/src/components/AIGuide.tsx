import React, { useMemo, useState, useEffect, useRef } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type SearchItem = { id: string; title?: string; url?: string | null; score: number; snippet?: string };
type Meta = {
  top_k: number;
  timing_ms: { embedding: number; search: number; llm: number; total: number };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  messages_preview?: { history_sent?: string[]; user?: string };
};
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[]; meta?: Meta | null };

export default function AIGuide(props: { apiBase?: string }) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const [mode, setMode] = useState<"search" | "ask">("search");
  const [q, setQ] = useState("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [apiOK, setApiOK] = useState<boolean | null>(null);

  const [results, setResults] = useState<SearchItem[]>([]);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const [lastMeta, setLastMeta] = useState<Meta | null>(null);
  const [debug, setDebug] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore PUBLIC_ Variablen werden beim Build ersetzt
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
    return () => { alive = false; };
  }, [apiBase]);

  // --- UI Helpers ---
  const MAX_TA_HEIGHT = 180;
  const autoSizeTA = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q, mode]);

  // Auto-Scroll zum neuesten Eintrag
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 12px",
    borderRadius: 8,
    border: active ? "1px solid #111" : "1px solid #ccc",
    background: active ? "#111" : "#fff",
    color: active ? "#fff" : "#111",
    cursor: "pointer",
  });

  async function doSearch() {
    setLoading(true); setErr(null); setResults([]);
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
    setLoading(true); setErr(null); setLastCitations([]); setLastMeta(null);
    try {
      const url = `${apiBase}/v1/chat${debug ? "?debug=1" : ""}`;
      const body: any = { question: q, top_k: k };
      if (conversationId) body.conversation_id = conversationId;

      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);

      const assistantText = (data.answer || "").trim();
      const citations = (data.citations || []) as Citation[];
      const meta = debug && data.meta ? (data.meta as Meta) : null;

      if (data.conversation_id && data.conversation_id !== conversationId) {
        setConversationId(data.conversation_id);
      }

      setMessages((prev) => [
        ...prev,
        { role: "user", content: q },
        { role: "assistant", content: assistantText, citations, meta },
      ]);
      setLastCitations(citations);
      setLastMeta(meta);
      setQ("");
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setMessages([]);
    setLastCitations([]);
    setLastMeta(null);
    setErr(null);
    setConversationId(null);
  }

  return (
    <div style={{ maxWidth: 900, margin: "2rem auto", padding: "1rem" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>AI-Guide</h1>

      <div style={{ fontSize: 14, opacity: 0.9, marginBottom: "1rem", display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
        API: <code>{apiBase}</code>
        {apiOK === null ? <span>· prüfe…</span> :
         apiOK ? <span style={{color:"#0a7"}}>· verbunden</span> :
                 <span style={{color:"#b00020"}}>· nicht erreichbar</span>}
        <label style={{ display:"flex", alignItems:"center", gap:6 }}>
          <input type="checkbox" checked={debug} onChange={(e)=>setDebug(e.target.checked)} />
          <span style={{ fontSize: 13 }}>Debug</span>
        </label>
        <input
          type="number" min={1} max={10} value={k}
          onChange={(e)=>setK(Number(e.target.value))}
          style={{ width: 64, padding: "6px 8px", borderRadius: 8, border: "1px solid #ccc" }}
          title="top_k"
        />
        <span style={{ fontSize: 12, opacity:.7 }}>
          {conversationId ? `Conv: ${conversationId.slice(0,8)}…` : "Conv: —"}
        </span>
        <button onClick={newChat}
                style={{ marginLeft: "auto", padding:"6px 10px", borderRadius: 8, border:"1px solid #ccc", background:"#fff", cursor:"pointer" }}>
          Neue Unterhaltung
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button onClick={() => setMode("search")} style={tabStyle(mode==="search")}>Search</button>
        <button onClick={() => setMode("ask")} style={tabStyle(mode==="ask")}>Ask</button>
      </div>

      {/* Antworten/Ergebnisse OBERHALB der Eingabe */}
      {mode==="search" && results.length>0 && (
        <div style={{ display: "grid", gap: 12, marginBottom: 12 }}>
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

      {mode==="ask" && (
        <>
          {messages.length > 0 && (
            <div
              ref={listRef}
              style={{
                maxHeight: "50vh",   // dynamisch (wächst mit Viewport)
                minHeight: 120,
                overflow: "auto",
                display:"grid",
                gap:10,
                marginBottom:12,
                paddingRight: 4,
              }}
            >
              {messages.map((m, idx)=>(
                <div key={idx} style={{ alignSelf: m.role === "user" ? "end" : "start", justifySelf: m.role === "user" ? "end" : "start", maxWidth:"100%" }}>
                  <div style={{
                    border: "1px solid #e5e7eb",
                    background: m.role === "user" ? "#111" : "#fff",
                    color: m.role === "user" ? "#fff" : "#111",
                    borderRadius: 12,
                    padding: "10px 12px",
                    boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                    whiteSpace: "pre-wrap"
                  }}>
                    <div style={{ fontSize:12, opacity:.7, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                    {m.content}
                  </div>
                  {m.role === "assistant" && idx === messages.length - 1 && lastCitations.length > 0 && (
                    <div style={{ border: "1px solid #eee", borderRadius: 10, padding: 10, marginTop:6 }}>
                      <div style={{ fontWeight: 600, marginBottom: 6 }}>Quellen</div>
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {lastCitations.map((c)=>(
                          <li key={c.id}>
                            {c.title || "(ohne Titel)"} {typeof c.score==="number" && <span style={{ opacity: .6 }}>· {c.score.toFixed(3)}</span>}
                            {c.url && <> – <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a></>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
              <div ref={endRef} />
            </div>
          )}

          {debug && lastMeta && (
            <div style={{ border: "1px dashed #bbb", borderRadius: 10, padding: 12, background:"#fafafa" }}>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <strong>Debug</strong>
                <span style={{ fontSize: 12, opacity:.7 }}>top_k {lastMeta.top_k}</span>
                <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
                  <button onClick={() => navigator.clipboard?.writeText(JSON.stringify(lastMeta,null,2)).catch(()=>{})}
                          style={{ fontSize:12, padding:"4px 8px", border:"1px solid #ccc", borderRadius:8, background:"#fff", cursor:"pointer" }}>
                    Copy meta
                  </button>
                  <details>
                    <summary style={{ cursor:"pointer", fontSize:12 }}>Raw JSON</summary>
                    <pre style={{ marginTop:8, maxHeight:240, overflow:"auto" }}>
{JSON.stringify(lastMeta, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>

              <div style={{ marginTop:10, display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))", gap:8 }}>
                <Stat label="Embedding" value={`${lastMeta.timing_ms.embedding} ms`} />
                <Stat label="Search" value={`${lastMeta.timing_ms.search} ms`} />
                <Stat label="LLM" value={`${lastMeta.timing_ms.llm} ms`} />
                <Stat label="Total" value={`${lastMeta.timing_ms.total} ms`} />
              </div>

              <div style={{ marginTop:10, display:"flex", gap:8, flexWrap:"wrap" }}>
                <Chip>Collection: <strong>{lastMeta.backend.collection}</strong></Chip>
                <Chip>Embed: <strong>{lastMeta.backend.embed_backend}</strong></Chip>
                <Chip>Model: <strong>{lastMeta.backend.chat_model}</strong></Chip>
                {lastMeta.token_usage && <Chip>Tokens: <strong>{lastMeta.token_usage.total_tokens ?? "-"}</strong></Chip>}
                {lastMeta.messages_preview?.history_sent && lastMeta.messages_preview.history_sent.length > 0 && (
                  <Chip>History: <strong>{lastMeta.messages_preview.history_sent.join(" → ")}</strong></Chip>
                )}
              </div>

              <div style={{ marginTop:12 }}>
                <div style={{ fontWeight:600, marginBottom:6 }}>Retrieval</div>
                <div style={{ display:"grid", gap:8 }}>
                  {lastMeta.retrieval.map((r)=>(
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
        </>
      )}

      {/* Eingabebereich (unten), mit Enter-to-send & Auto-Resize */}
      <textarea
        ref={taRef}
        value={q}
        onChange={(e)=>setQ(e.target.value)}
        onInput={autoSizeTA}
        onFocus={autoSizeTA}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!q.trim() || apiOK === false || loading) return;
            mode === "search" ? doSearch() : doAsk();
          }
        }}
        placeholder={mode==="search" ? "Suche (z. B. nonuse loader)" : "Frage stellen…"}
        rows={1}
        style={{
          width: "100%",
          padding: 12,
          borderRadius: 8,
          border: "1px solid #ccc",
          marginTop: 8,
          marginBottom: 12,
          resize: "none",
          lineHeight: "1.4",
        }}
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
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"8px 10px" }}>
      <div style={{ fontSize:12, opacity:.7 }}>{label}</div>
      <div style={{ fontWeight:600 }}>{value}</div>
    </div>
  );
}
function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontSize:12, border:"1px solid #ddd", borderRadius:16, padding:"4px 10px", background:"#fff" }}>
      {children}
    </span>
  );
}