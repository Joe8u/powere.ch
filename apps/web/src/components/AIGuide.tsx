// apps/web/src/components/AIGuide.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

// ---------- Typen ----------
type Citation = { id: string; title?: string; url?: string | null; score?: number };
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

type Meta = {
  top_k: number;
  timing_ms: { embedding: number | null; search: number | null; llm: number | null; total: number | null };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
  messages_preview?: { history_sent?: string[]; user?: string } | null;
};

// ---------- Helpers ----------
const LS_KEY_CID = "aiGuide.convId.v1";
const LS_KEY_TOPK = "aiGuide.topk.v1";
const LS_KEY_DEBUG = "aiGuide.debug.v1";

// Theme aus Starlight-Variablen lesen (Dark/Light sicher)
function useThemeVars() {
  const get = (v: string, fallback: string) =>
    typeof window !== "undefined"
      ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fallback
      : fallback;

  return {
    bg:       get("--sl-color-bg", "#fff"),
    text:     get("--sl-color-text", "#111"),
    border:   get("--sl-color-gray-5", "#e5e7eb"),
    headerBg: get("--sl-color-gray-6", "#f7f7f8"),
    muted:    get("--sl-color-gray-3", "#d1d5db"),
    brand:    get("--sl-color-accent", "#111"),
  };
}

function Spinner({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-label="Lädt…"
    >
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
    ALLOWED_TAGS: [
      "p","br","strong","em","code","pre","blockquote","ul","ol","li","a","h1","h2","h3","h4","h5","h6","table","thead","tbody","tr","th","td"
    ],
    ALLOWED_ATTR: ["href","target","rel","class"],
  });
}

// SSE-Client (einfacher Parser)
function createSSEStream(
  url: string,
  body: any,
  onEvent: (ev: string, data: any) => void,
  abortSignal?: AbortSignal
) {
  const controller = new AbortController();

  const promise = (async () => {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Accept": "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abortSignal ?? controller.signal,
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

// ---------- Component ----------
export default function AIGuide(props: { apiBase?: string }) {
  const theme = useThemeVars();

  // API Base
  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore – beim Build ersetzt
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:9000`;
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // Reachability
  const [apiOK, setApiOK] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/ping`);
        if (!alive) return;
        setApiOK(r.ok);
      } catch {
        if (!alive) return;
        setApiOK(false);
      }
    })();
    return () => { alive = false; };
  }, [apiBase]);

  // State
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [k, setK] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const v = window.localStorage.getItem(LS_KEY_TOPK);
      if (v) return Math.max(1, Math.min(10, Number(v) || 5));
    }
    return 5;
  });
  const [debugFlag, setDebugFlag] = useState<boolean>(() => {
    if (typeof window !== "undefined") return window.localStorage.getItem(LS_KEY_DEBUG) === "1";
    return true;
  });
  const [loading, setLoading] = useState(false);

  // Analyse-Zustände
  const [lastMeta, setLastMeta] = useState<Meta | null>(null);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const [eventLog, setEventLog] = useState<string[]>([]);

  // persist
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (conversationId) window.localStorage.setItem(LS_KEY_CID, conversationId);
      else window.localStorage.removeItem(LS_KEY_CID);
    }
  }, [conversationId]);
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cid = window.localStorage.getItem(LS_KEY_CID);
      if (cid) setConversationId(cid);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(LS_KEY_TOPK, String(k));
  }, [k]);
  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(LS_KEY_DEBUG, debugFlag ? "1" : "0");
  }, [debugFlag]);

  // Scroll an das Ende
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // Textarea autosize
  const MAX_TA_HEIGHT = 200;
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const autoSizeTA = () => {
    const el = taRef.current; if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q]);

  // Tabs im Analysebereich
  const [panelTab, setPanelTab] = useState<"debug" | "retrieval" | "events" | "analysis-json">("debug");

  // Hilfs-Renderer
  const MD = ({ text }: { text: string }) =>
    <div className="ai-md" style={{ lineHeight: 1.55 }} dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />;

  // Streaming-Senden
  const assistantIdxRef = useRef<number>(-1);
  async function send() {
    if (!q.trim() || loading || apiOK === false) return;
    setLoading(true);
    setEventLog([]);

    // Optimistic UI: user + leere assistant
    setMessages((prev) => {
        const userMsg: Msg = { role: "user", content: q };
        const assistantMsg: Msg = { role: "assistant", content: "" };
        const next: Msg[] = [...prev, userMsg, assistantMsg];
        assistantIdxRef.current = next.length - 1;
        return next;
    });

    const body: any = { question: q, top_k: k };
    if (conversationId) body.conversation_id = conversationId;

    // Timeouts / Fallback
    let gotFirstToken = false;
    const firstTokenWatch = window.setTimeout(() => {
      if (!gotFirstToken) abortAndFallback();
    }, 6000);
    const hardWatch = window.setTimeout(() => setLoading(false), 45000);

    function log(ev: string, payload: any) {
      setEventLog(prev => {
        const ts = new Date().toISOString().split("T")[1].replace("Z","");
        const line = `${ts}  ${ev}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`;
        const trimmed = prev.length > 600 ? prev.slice(-600) : prev;
        return [...trimmed, line];
      });
    }

    const streamURL = `${apiBase}/v1/chat/stream${debugFlag ? "?debug=1" : ""}`;
    const { controller, promise } = createSSEStream(streamURL, body, (ev, data) => {
      if (ev === "meta") {
        log(ev, data);
        if (data?.conversation_id && data.conversation_id !== conversationId) setConversationId(data.conversation_id);
        if (Array.isArray(data?.citations)) setLastCitations(data.citations as Citation[]);
        if (data?.meta) setLastMeta(data.meta as Meta);
      } else if (ev === "token") {
        const delta = (data && typeof data.delta === "string") ? data.delta : "";
        if (!delta) return;
        gotFirstToken = true;
        setMessages(prev => {
          const next = prev.slice();
          const i = Math.min(Math.max(assistantIdxRef.current, 0), next.length - 1);
          if (next[i] && next[i].role === "assistant") {
            next[i] = { ...next[i], content: (next[i].content || "") + delta };
          }
          return next;
        });
      } else if (ev === "done") {
        log(ev, data);
        if (data?.meta) setLastMeta(data.meta as Meta);
        setLoading(false);
      } else {
        // unbekanntes Event
        log(ev, data);
      }
    });

    async function abortAndFallback() {
      try { controller.abort(); } catch {}
      try {
        const url = `${apiBase}/v1/chat${debugFlag ? "?debug=1" : ""}`;
        const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const data = await r.json();
        if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);
        if (data?.conversation_id && data.conversation_id !== conversationId) setConversationId(data.conversation_id);
        setLastCitations((data?.citations || []) as Citation[]);
        setLastMeta(data?.meta || null);
        setMessages(prev => {
          const next = prev.slice();
          const i = Math.min(Math.max(assistantIdxRef.current, 0), next.length - 1);
          if (next[i] && next[i].role === "assistant") {
            next[i] = { role: "assistant", content: (data.answer || "").trim(), citations: data.citations || [] };
          }
          return next;
        });
      } catch (e: any) {
        setMessages(prev => {
          const next = prev.slice();
          const i = Math.min(Math.max(assistantIdxRef.current, 0), next.length - 1);
          if (next[i] && next[i].role === "assistant") {
            next[i] = { role: "assistant", content: `⚠ ${e.message || String(e)}` };
          }
          return next;
        });
      } finally {
        setLoading(false);
      }
    }

    try {
      await promise;
    } catch {
      await abortAndFallback();
    } finally {
      window.clearTimeout(firstTokenWatch);
      window.clearTimeout(hardWatch);
      setQ("");
      setTimeout(() => taRef.current?.focus(), 0);
    }
  }

  function resetConversation() {
    setMessages([]);
    setLastMeta(null);
    setLastCitations([]);
    setEventLog([]);
    setConversationId(null);
    setQ("");
  }

  // Analyse-JSON (leicht „LLM-freundlich“)
  const analysisJSON = useMemo(() => {
    const lastAssistant = [...messages].reverse().find(m => m.role === "assistant");
    const lastUser = [...messages].reverse().find(m => m.role === "user");
    return JSON.stringify({
      conversation_id: conversationId,
      question: lastUser?.content ?? null,
      answer_preview: lastAssistant?.content?.slice(0, 280) ?? null,
      top_k: k,
      citations: lastCitations,
      meta: lastMeta,
      api_ok: apiOK,
      model: lastMeta?.backend?.chat_model,
      collection: lastMeta?.backend?.collection,
    }, null, 2);
  }, [conversationId, messages, k, lastCitations, lastMeta, apiOK]);

  // UI
  return (
    <div style={{ maxWidth: 1200, margin: "1.5rem auto", padding: "0 1rem" }}>
      {/* Kopfzeile */}
      <div
        style={{
          display:"flex", gap:12, alignItems:"center", marginBottom: 12,
          border:`1px solid ${theme.border}`, borderRadius: 12, padding: "10px 12px", background: theme.headerBg
        }}
      >
        <strong>AI-Guide Studio</strong>
        <span style={{ fontSize: 12, opacity:.75 }}>
          {apiOK === null ? "API prüfen…" : apiOK ? "verbunden" : "offline"}
        </span>
        <span style={{ fontSize: 12, opacity:.65 }}>
          {conversationId ? `CID ${conversationId.slice(0,8)}…` : "neue Unterhaltung"}
        </span>
        <div style={{ marginLeft: "auto", display:"flex", gap:8, alignItems:"center" }}>
          <label style={{ display:"flex", gap:6, alignItems:"center", fontSize:13 }}>
            <input type="checkbox" checked={debugFlag} onChange={(e)=>setDebugFlag(e.target.checked)} />
            Debug
          </label>
          <label style={{ display:"flex", gap:6, alignItems:"center", fontSize:13 }}>
            top_k
            <input
              type="number" min={1} max={10} value={k}
              onChange={(e)=>setK(Math.max(1,Math.min(10,Number(e.target.value)||5)))}
              style={{ width:64, padding:"4px 6px", borderRadius:8, border:`1px solid ${theme.muted}`, background: theme.bg, color: theme.text }}
            />
          </label>
          <button onClick={resetConversation}
            style={{ padding:"6px 10px", borderRadius:8, border:`1px solid ${theme.muted}`, background: theme.bg, cursor:"pointer" }}>
            Reset
          </button>
        </div>
      </div>

      {/* 2-Spalten Layout: links Chat, rechts Analyse */}
      <div style={{
        display:"grid",
        gridTemplateColumns: "minmax(320px, 1fr) 380px",
        gap: 14
      }}>
        {/* Chat-Spalte */}
        <div style={{ border:`1px solid ${theme.border}`, borderRadius:12, overflow:"hidden", background: theme.bg }}>
          {/* Chat-Verlauf */}
          <div style={{ maxHeight: "60vh", overflow:"auto", padding: 12, display:"grid", gap:10 }}>
            {messages.length === 0 && (
              <div style={{ fontSize:13, opacity:.75 }}>
                Starte mit einer Frage. Antworten werden live gestreamt.  
                <br/>Hinweis: Antworten basieren ausschließlich auf dem internen Kontext (RAG).
              </div>
            )}
            {messages.map((m, idx) => (
              <div key={idx} style={{ justifySelf: m.role === "user" ? "end" : "start", maxWidth:"100%" }}>
                <div style={{
                  border: `1px solid ${theme.border}`,
                  background: m.role === "user" ? theme.brand : theme.bg,
                  color: m.role === "user" ? "#fff" : theme.text,
                  borderRadius: 12,
                  padding: "10px 12px",
                  boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  whiteSpace: "pre-wrap",
                }}>
                  <div style={{ fontSize:12, opacity:.7, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                  {m.role === "assistant"
                    ? (m.content
                        ? <MD text={m.content} />
                        : <div style={{ display:"flex", alignItems:"center", gap:8 }}><Spinner size={16} color={theme.text} /><span>Antwort wird generiert…</span></div>
                      )
                    : m.content}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div style={{ border: `1px solid ${theme.border}`, borderRadius: 10, padding: 8, marginTop:6 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4, fontSize:13 }}>Quellen</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {m.citations.map((c)=>(
                        <li key={c.id} style={{ fontSize: 12 }}>
                          {c.title || "(ohne Titel)"} {typeof c.score==="number" && <span style={{ opacity: .6 }}>· {c.score.toFixed(3)}</span>}
                          {c.url && <> – <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a></>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
            {/* Live-Spinner, falls letzte Assistant-Bubble noch leer ist */}
            {loading && messages[messages.length-1]?.role === "assistant" && !messages[messages.length-1]?.content && (
              <div style={{ justifySelf: "start" }}>
                <div style={{ border:`1px solid ${theme.border}`, borderRadius:12, padding:"10px 12px" }}>
                  <div style={{ fontSize:12, opacity:.7, marginBottom:4 }}>AI-Guide</div>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <Spinner size={16} color={theme.text} />
                    <span>Antwort wird generiert…</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Eingabe unten */}
          <div style={{ borderTop:`1px solid ${theme.border}`, padding: 10 }}>
            <textarea
              ref={taRef}
              value={q}
              onChange={(e)=>setQ(e.target.value)}
              onInput={autoSizeTA}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
              }}
              placeholder="Frage stellen… (Enter = senden, Shift+Enter = Zeilenumbruch)"
              rows={1}
              style={{
                width: "100%", padding: 10, borderRadius: 10,
                border: `1px solid ${theme.border}`,
                background: theme.bg, color: theme.text,
                lineHeight: "1.45", resize: "none", maxHeight: MAX_TA_HEIGHT, overflowY: "auto", marginBottom: 8
              }}
            />
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{ padding:"8px 12px", borderRadius:10, border:`1px solid ${theme.text}`, background: theme.text, color:"#fff", cursor:"pointer", display:"inline-flex", alignItems:"center", gap:8 }}
              >
                {loading ? (<><Spinner size={16} color="#fff" /> Senden…</>) : "Senden"}
              </button>
            </div>
          </div>
        </div>

        {/* Analyse-Spalte */}
        <div style={{ border:`1px solid ${theme.border}`, borderRadius:12, overflow:"hidden", background: theme.bg }}>
          {/* Tabs */}
          <div style={{ display:"flex", gap:8, padding:10, borderBottom:`1px solid ${theme.border}`, background: theme.headerBg }}>
            {(["debug","retrieval","events","analysis-json"] as const).map(tab => (
              <button
                key={tab}
                onClick={()=>setPanelTab(tab)}
                style={{
                  padding:"6px 10px", borderRadius:8, cursor:"pointer",
                  border: `1px solid ${panelTab===tab ? theme.text : theme.muted}`,
                  background: panelTab===tab ? theme.text : theme.bg,
                  color: panelTab===tab ? "#fff" : theme.text,
                  fontSize: 12, textTransform:"uppercase", letterSpacing: ".02em"
                }}
              >
                {tab === "debug" ? "Debug" : tab === "retrieval" ? "Retrieval" : tab === "events" ? "Events" : "Analysis JSON"}
              </button>
            ))}
            <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
              <button
                onClick={() => { navigator.clipboard?.writeText(analysisJSON).catch(()=>{}); }}
                style={{ padding:"6px 10px", borderRadius:8, border:`1px solid ${theme.muted}`, background: theme.bg, cursor:"pointer", fontSize:12 }}
              >
                Copy Analysis
              </button>
            </div>
          </div>

          {/* Panel-Inhalte */}
          <div style={{ padding:12, maxHeight: "60vh", overflow:"auto" }}>
            {panelTab === "debug" && (
              <>
                {!lastMeta && <div style={{ fontSize:13, opacity:.75 }}>Noch keine Debug-Daten. Sende eine Frage mit aktivem <em>Debug</em>-Schalter.</div>}
                {lastMeta && (
                  <div style={{ display:"grid", gap:12 }}>
                    {/* Timings */}
                    <div>
                      <div style={{ fontWeight:600, marginBottom:6 }}>Timings</div>
                      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(120px,1fr))", gap:8 }}>
                        <Stat label="Embedding" value={fmtMs(lastMeta.timing_ms.embedding)} />
                        <Stat label="Search" value={fmtMs(lastMeta.timing_ms.search)} />
                        <Stat label="LLM" value={fmtMs(lastMeta.timing_ms.llm)} />
                        <Stat label="Total" value={fmtMs(lastMeta.timing_ms.total)} />
                      </div>
                    </div>
                    {/* Backend */}
                    <div>
                      <div style={{ fontWeight:600, marginBottom:6 }}>Backend</div>
                      <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
                        <Chip>Collection: <strong>{lastMeta.backend.collection}</strong></Chip>
                        <Chip>Embed: <strong>{lastMeta.backend.embed_backend}</strong></Chip>
                        <Chip>Model: <strong>{lastMeta.backend.chat_model}</strong></Chip>
                        {lastMeta.token_usage && <Chip>Tokens: <strong>{lastMeta.token_usage.total_tokens ?? "-"}</strong></Chip>}
                        {lastMeta.messages_preview?.history_sent?.length ? (
                          <Chip>History: <strong>{lastMeta.messages_preview.history_sent.join(" → ")}</strong></Chip>
                        ) : null}
                      </div>
                    </div>
                    {/* Prompt-Preview */}
                    {lastMeta.messages_preview?.user && (
                      <div>
                        <div style={{ fontWeight:600, marginBottom:6 }}>User-Prompt (Preview)</div>
                        <pre style={preStyle(theme)}>{lastMeta.messages_preview.user}</pre>
                      </div>
                    )}
                    {/* Citations */}
                    {lastCitations?.length ? (
                      <div>
                        <div style={{ fontWeight:600, marginBottom:6 }}>Citations</div>
                        <ul style={{ margin:0, paddingLeft:18 }}>
                          {lastCitations.map((c)=>(
                            <li key={c.id} style={{ fontSize:13 }}>
                              {c.title || "(ohne Titel)"} {typeof c.score==="number" && <span style={{ opacity:.6 }}>· {c.score.toFixed(3)}</span>}
                              {c.url && <> – <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a></>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                )}
              </>
            )}

            {panelTab === "retrieval" && (
              <>
                {!lastMeta?.retrieval?.length && <div style={{ fontSize:13, opacity:.75 }}>Keine Retrieval-Daten vorhanden.</div>}
                {lastMeta?.retrieval?.length ? (
                  <div style={{ display:"grid", gap:8 }}>
                    {lastMeta.retrieval.map((r)=>(
                      <div key={`${r.rank}-${r.id}`} style={{ border:`1px solid ${theme.border}`, borderRadius:8, padding:10 }}>
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
                ) : null}
              </>
            )}

            {panelTab === "events" && (
              <pre style={preStyle(theme)}>{eventLog.length ? eventLog.join("\n") : "// noch keine Events"}</pre>
            )}

            {panelTab === "analysis-json" && (
              <pre style={preStyle(theme)}>{analysisJSON}</pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- UI Bausteine ----------
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ border:"1px solid var(--sl-color-gray-5, #e5e7eb)", borderRadius:8, padding:"8px 10px" }}>
      <div style={{ fontSize:12, opacity:.7 }}>{label}</div>
      <div style={{ fontWeight:600 }}>{value}</div>
    </div>
  );
}
function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      fontSize:12, border:"1px solid var(--sl-color-gray-5, #e5e7eb)",
      borderRadius:16, padding:"4px 10px", background:"var(--sl-color-bg, #fff)"
    }}>
      {children}
    </span>
  );
}
function preStyle(theme: ReturnType<typeof useThemeVars>): React.CSSProperties {
  return {
    background: theme.headerBg,
    color: theme.text,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 10,
    margin: 0,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
    fontSize: 12,
    lineHeight: 1.5,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  };
}
function fmtMs(v: number | null) {
  return v == null ? "–" : `${v} ms`;
}