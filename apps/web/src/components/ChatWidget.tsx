import React, { useEffect, useMemo, useRef, useState } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type Meta = {
  top_k: number;
  timing_ms: { embedding: number; search: number; llm: number; total: number };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  messages_preview?: { history_sent?: string[]; user?: string };
};
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[]; meta?: Meta | null };

const LS_KEY = "aiGuide.convId.v1";

export default function ChatWidget(props: { apiBase?: string; suppressOnGuide?: boolean }) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  // hide widget on /guide (Seite hat schon den großen AI-Guide)
  useEffect(() => {
    if (props.suppressOnGuide === false) return;
    if (typeof window !== "undefined") {
      setHidden(window.location.pathname.startsWith("/guide"));
    }
  }, [props.suppressOnGuide]);

  const [apiOK, setApiOK] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  // restore convId from localStorage so the chat continues across pages
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cid = window.localStorage.getItem(LS_KEY);
      if (cid) setConversationId(cid);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (conversationId) window.localStorage.setItem(LS_KEY, conversationId);
      else window.localStorage.removeItem(LS_KEY);
    }
  }, [conversationId]);

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

  // ping API
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
    return () => { alive = false };
  }, [apiBase]);

  // auto-scroll to newest message
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open]);

  // auto-resize textarea (like ChatGPT)
  const MAX_TA_HEIGHT = 180;
  const autoSizeTA = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q, open]);

  async function send() {
    if (!q.trim() || loading || apiOK === false) return;
    setLoading(true);
    try {
      const url = `${apiBase}/v1/chat`;
      const body: any = { question: q, top_k: 5 };
      if (conversationId) body.conversation_id = conversationId;

      // optimistic UI: add user message immediately
      setMessages((prev) => [...prev, { role: "user", content: q }]);

      const r = await fetch(url, {
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

      setMessages((prev) => [...prev, { role: "assistant", content: answer, citations }]);
      setQ("");
      // focus back to textarea
      setTimeout(() => taRef.current?.focus(), 0);
    } catch (e:any) {
      setMessages((prev) => [...prev, { role: "assistant", content: `⚠ ${e.message || String(e)}` }]);
    } finally {
      setLoading(false);
    }
  }

  function resetChat() {
    setMessages([]);
    setConversationId(null);
    setQ("");
  }

  if (hidden) return null;

  return (
    <>
      {/* Floating bubble */}
      <button
        aria-label="AI-Guide öffnen"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          right: 20, bottom: 20,
          width: 56, height: 56,
          borderRadius: 999,
          background: "#111", color: "#fff",
          border: "1px solid #333",
          boxShadow: "0 10px 24px rgba(0,0,0,.18)",
          zIndex: 9999,
          display: "grid", placeItems: "center",
          cursor: "pointer",
        }}
        title={apiOK === false ? "API nicht erreichbar" : "AI-Guide"}
      >
        {/* tiny status dot */}
        <span style={{
          position:"absolute", top:8, right:8, width:8, height:8, borderRadius:99,
          background: apiOK ? "#0a7" : "#b00020"
        }} />
        {/* robot icon */}
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11 2a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v6a5 5 0 0 1-5 5h-6a5 5 0 0 1-5-5V9a3 3 0 0 1 3-3h1V5a2 2 0 0 1 2-2h1V2Zm-4 7a1 1 0 1 0 0 2h1a1 1 0 1 0 0-2H7Zm9 0h1a1 1 0 1 1 0 2h-1a1 1 0 1 1 0-2ZM8 14a1 1 0 1 0 0 2h8a1 1 0 1 0 0-2H8Z"/>
        </svg>
      </button>

      {/* Panel */}
      {open && (
        <div
          role="dialog"
          aria-label="AI-Guide"
          style={{
            position: "fixed",
            right: 16, bottom: 84,
            width: "min(420px, 92vw)",
            height: "min(70vh, 600px)",
            background: "#fff",
            color: "#111",
            border: "1px solid #e5e7eb",
            borderRadius: 16,
            boxShadow: "0 16px 56px rgba(0,0,0,.22)",
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* header */}
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #eee", display:"flex", alignItems:"center", gap:8 }}>
            <strong style={{ fontWeight:700 }}>AI-Guide</strong>
            <span style={{ fontSize:12, opacity:.7 }}>
              {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
            </span>
            <span style={{ marginLeft:"auto", fontSize: 11, opacity:.65 }}>
              {conversationId ? `Conv ${conversationId.slice(0,8)}…` : "neue Unterhaltung"}
            </span>
            <button onClick={resetChat}
              style={{ marginLeft:8, fontSize:12, padding:"4px 8px", border:"1px solid #ddd", borderRadius:8, background:"#fff", cursor:"pointer" }}>
              Reset
            </button>
            <button onClick={() => setOpen(false)}
              aria-label="schließen"
              style={{ marginLeft:8, width:28, height:28, borderRadius:8, border:"1px solid #ddd", background:"#fff", cursor:"pointer" }}>
              ✕
            </button>
          </div>

          {/* messages */}
          <div style={{ flex: 1, overflow: "auto", padding: 12, display:"grid", gap:10 }}>
            {messages.length === 0 && (
              <div style={{ fontSize:13, opacity:.75 }}>
                Hallo! Stell mir eine Frage zu powere.ch, Daten, Loaders oder Methodik.
                <br/>Tipp: <span style={{fontFamily:"monospace"}}>Shift+Enter</span> → neue Zeile, <span style={{fontFamily:"monospace"}}>Enter</span> → senden.
              </div>
            )}
            {messages.map((m, idx) => (
              <div key={idx} style={{ justifySelf: m.role === "user" ? "end" : "start", maxWidth:"100%" }}>
                <div style={{
                  border: "1px solid #e5e7eb",
                  background: m.role === "user" ? "#111" : "#fff",
                  color: m.role === "user" ? "#fff" : "#111",
                  borderRadius: 12,
                  padding: "10px 12px",
                  boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  whiteSpace: "pre-wrap",
                }}>
                  <div style={{ fontSize:12, opacity:.65, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                  {m.content}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div style={{ border: "1px solid #eee", borderRadius: 10, padding: 8, marginTop:6 }}>
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
            <div ref={endRef} />
          </div>

          {/* input */}
          <div style={{ padding: 10, borderTop: "1px solid #eee" }}>
            <textarea
              ref={taRef}
              value={q}
              onChange={(e)=>setQ(e.target.value)}
              onInput={autoSizeTA}
              onFocus={autoSizeTA}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
                if (e.key === "Escape") setOpen(false);
              }}
              placeholder="Frage stellen… (Enter = senden, Shift+Enter = Zeilenumbruch)"
              rows={1}
              style={{
                width: "100%",
                padding: 10,
                borderRadius: 10,
                border: "1px solid #ddd",
                resize: "none",
                lineHeight: "1.4",
                maxHeight: MAX_TA_HEIGHT,
                overflowY: "auto",
                marginBottom: 8,
              }}
            />
            <div style={{ display:"flex", gap:8, justifyContent:"space-between" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{ padding:"8px 12px", borderRadius:10, border:"1px solid #333", background:"#111", color:"#fff", cursor:"pointer" }}
              >
                {loading ? "Senden…" : "Senden"}
              </button>
              <span style={{ fontSize: 11, opacity:.6 }}>
                {apiOK === false ? "API offline" : conversationId ? `Conv ${conversationId.slice(0,8)}…` : "neu"}
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}