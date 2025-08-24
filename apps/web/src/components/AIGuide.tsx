import React, { useMemo, useState, useEffect, useRef } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type SearchItem = { id: string; title?: string; url?: string | null; score: number; snippet?: string };
type Meta = {
  top_k: number;
  timing_ms: { embedding: number; search: number; llm: number | null; total: number | null };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
  messages_preview?: { history_sent?: string[]; user?: string } | null;
};
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
         aria-label="Lädt…">
      <circle cx="12" cy="12" r="9" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.9s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function renderMarkdown(md: string): string {
  const html = marked.parse(md, { breaks: true }) as string;
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["p","br","strong","em","code","pre","blockquote","ul","ol","li","a","h1","h2","h3","h4"],
    ALLOWED_ATTR: ["href","target","rel","class"],
  });
}

function createSSEStream(
  url: string,
  body: any,
  onEvent: (ev: string, data: any) => void,
  abortSignal?: AbortSignal
) {
  const controller = new AbortController();
  const signal = abortSignal ?? controller.signal;

  const promise = (async () => {
    const r = await fetch(url, {
      method: "POST",
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!r.ok || !r.body) throw new Error(`HTTP ${r.status} ${r.statusText}`);

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      buf = buf.replace(/\r\n/g, "\n");
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);

        let ev = "message";
        const dataLines: string[] = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) ev = line.slice(6).trim().toLowerCase();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length) {
          const dataStr = dataLines.join("\n");
          try { onEvent(ev, JSON.parse(dataStr)); }
          catch { onEvent(ev, { raw: dataStr }); }
        }
      }
    }
  })();

  return { controller, promise };
}

export default function AIGuide(props: { apiBase?: string }) {
  const [mode, setMode] = useState<"search" | "ask">("search");
  const [q, setQ] = useState("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [apiOK, setApiOK] = useState<boolean | null>(null);

  // Search
  const [results, setResults] = useState<SearchItem[]>([]);

  // Ask
  const [messages, setMessages] = useState<Msg[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const [lastMeta, setLastMeta] = useState<Meta | null>(null);
  const [debug, setDebug] = useState(false);

  const endRef = useRef<HTMLDivElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:9000`;
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // ping API
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/ping`);
        if (!alive) return;
        setApiOK(r.ok);
      } catch { if (!alive) return; setApiOK(false); }
    })();
    return () => { alive = false; };
  }, [apiBase]);

  // auto-scroll
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  // textarea autosize
  const MAX_TA_HEIGHT = 180;
  const autoSizeTA = () => {
    const el = taRef.current; if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q, mode]);

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
    if (!q.trim() || apiOK === false) return;

    setErr(null);
    setLastCitations([]);
    setLastMeta(null);
    setLoading(true);

    // optimistic messages
    setMessages((prev) => [...prev, { role: "user", content: q }, { role: "assistant", content: "" }]);
    const assistantIdx = messages.length + 1;

    const body: any = { question: q, top_k: k };
    if (conversationId) body.conversation_id = conversationId;

    // watchdogs
    let gotFirstToken = false;
    const tokenTimeout = window.setTimeout(() => {
      if (!gotFirstToken) stopAndFallback();
    }, 6000);
    const hardTimeout = window.setTimeout(() => {
      setLoading(false);
    }, 30000);

    // start stream
    const url = `${apiBase}/v1/chat/stream${debug ? "?debug=1" : ""}`;
    const controller = new AbortController();
    abortRef.current = controller;

    const { promise } = createSSEStream(url, body, (ev, data) => {
      if (ev === "meta") {
        if (data?.conversation_id && data.conversation_id !== conversationId) {
          setConversationId(data.conversation_id);
        }
        if (Array.isArray(data?.citations)) {
          setLastCitations(data.citations as Citation[]);
          setMessages((prev) => {
            const next = prev.slice();
            const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
            if (next[idx] && next[idx].role === "assistant") {
              next[idx] = { ...next[idx], citations: data.citations as Citation[] };
            }
            return next;
          });
        }
        if (data?.meta) setLastMeta(data.meta as Meta);
      } else if (ev === "token") {
        const delta = typeof data?.delta === "string" ? data.delta : "";
        if (!delta) return;
        gotFirstToken = true;
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { ...next[idx], content: (next[idx].content || "") + delta };
          }
          return next;
        });
      } else if (ev === "done") {
        setLoading(false);
      }
    }, controller.signal);

    const stopAndFallback = async () => {
      try { controller.abort(); } catch {}
      try {
        const r = await fetch(`${apiBase}/v1/chat${debug ? "?debug=1" : ""}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);
        const answer = (data.answer || "").trim();
        const citations = (data.citations || []) as Citation[];
        if (data.conversation_id && data.conversation_id !== conversationId) {
          setConversationId(data.conversation_id);
        }
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { role: "assistant", content: answer, citations };
          }
          return next;
        });
        if (debug && data.meta) setLastMeta(data.meta as Meta);
      } catch (e2: any) {
        setErr(e2.message || String(e2));
      } finally {
        setLoading(false);
      }
    };

    try {
      await promise;
    } catch {
      await stopAndFallback();
    } finally {
      window.clearTimeout(tokenTimeout);
      window.clearTimeout(hardTimeout);
      setQ("");
      setTimeout(() => taRef.current?.focus(), 0);
      abortRef.current = null;
    }
  }

  function stopGenerating() {
    try { abortRef.current?.abort(); } catch {}
    abortRef.current = null;
    setLoading(false);
  }

  function newChat() {
    setMessages([]);
    setLastCitations([]);
    setLastMeta(null);
    setErr(null);
    setConversationId(null);
    try { abortRef.current?.abort(); } catch {}
    abortRef.current = null;
  }

  const waitingOnAssistant =
    loading &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant" &&
    (messages[messages.length - 1].content || "").length === 0;

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

      <textarea
        ref={taRef}
        value={q}
        onChange={(e)=>setQ(e.target.value)}
        onInput={autoSizeTA}
        placeholder={mode==="search" ? "Suche (z. B. nonuse loader)" : "Frage stellen…"}
        rows={1}
        style={{ width: "100%", padding: 12, borderRadius: 8, border: "1px solid #ccc", marginBottom: 12, resize:"none", lineHeight:"1.4", maxHeight:180, overflowY:"auto" }}
      />
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {mode==="search" ? (
          <button onClick={doSearch} disabled={loading || !q.trim() || apiOK === false}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
            {loading ? "Suchen…" : "Search"}
          </button>
        ) : (
          <>
            <button onClick={doAsk} disabled={loading || !q.trim() || apiOK === false}
              style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}>
              {loading ? (<span style={{display:"inline-flex",alignItems:"center",gap:8}}><Spinner />Senden…</span>) : "Ask"}
            </button>
            <button onClick={stopGenerating} disabled={!loading}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #ccc", background: "#fff", color: "#111", cursor: loading ? "pointer" : "not-allowed" }}>
              Stop
            </button>
          </>
        )}
      </div>

      {err && <div style={{ color: "#b00020", marginBottom: 12 }}>⚠ {err}</div>}

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

      {mode==="ask" && (
        <>
          {messages.length > 0 && (
            <div style={{ display:"grid", gap:10, marginBottom:12 }}>
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
                    {m.role === "assistant"
                      ? (m.content
                          ? <div className="ai-md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                          : <div style={{ display:"flex", alignItems:"center", gap:8 }}><Spinner /> <span style={{opacity:.7}}>Antwort wird generiert…</span></div>
                        )
                      : m.content}
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
            </div>
          )}

          {debug && lastMeta && (
            <div style={{ border: "1px dashed #bbb", borderRadius: 10, padding: 12, background:"#fafafa" }}>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <strong>Debug</strong>
                <span style={{ fontSize: 12, opacity:.7 }}>top_k {lastMeta.top_k}</span>
              </div>

              <div style={{ marginTop:10, display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))", gap:8 }}>
                <Stat label="Embedding" value={`${lastMeta.timing_ms.embedding} ms`} />
                <Stat label="Search" value={`${lastMeta.timing_ms.search} ms`} />
                <Stat label="LLM" value={`${lastMeta.timing_ms.llm ?? "-"} ms`} />
                <Stat label="Total" value={`${lastMeta.timing_ms.total ?? "-"} ms`} />
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
      <div ref={endRef} />
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