import React, { useEffect, useMemo, useRef, useState } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

const LS_CID  = "aiGuide.convId.v1";
const LS_SIZE = "aiGuide.widget.size.v1";

export default function ChatWidget(props: { apiBase?: string; suppressOnGuide?: boolean }) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  // API & Chat-State
  const [apiOK, setApiOK] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  // Panel-Geometrie (oben links unter Header)
  const [panelTop, setPanelTop] = useState<number>(72);
  const [width, setWidth] = useState<number>(380);
  const [height, setHeight] = useState<number>(520);

  const taRef  = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const resizeState = useRef<{ startX: number; startY: number; startW: number; startH: number; active: boolean } | null>(null);

  // Farben aus Starlight-Tokens
  const COLORS = {
    bg:        "var(--sl-color-bg)",
    bgSoft:    "var(--sl-color-bg-soft)",
    text:      "var(--sl-color-text)",
    hairline:  "var(--sl-color-hairline)",
  } as const;

  // Bubble auf /guide optional ausblenden (dort gibt's die große Seite)
  useEffect(() => {
    if (props.suppressOnGuide === false) return;
    if (typeof window !== "undefined") setHidden(window.location.pathname.startsWith("/guide"));
  }, [props.suppressOnGuide]);

  // API-Basis
  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:9000`;
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // Headerhöhe messen → Panel direkt drunter (oben links)
  useEffect(() => {
    function computeTop() {
      const header =
        (document.querySelector('header[role="banner"]') as HTMLElement) ||
        (document.querySelector("header") as HTMLElement) || null;
      const h = header?.offsetHeight ?? 64;
      setPanelTop(h + 8);
    }
    computeTop();
    window.addEventListener("resize", computeTop);
    return () => window.removeEventListener("resize", computeTop);
  }, []);

  // Größe aus/in LocalStorage
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(LS_SIZE);
      if (raw) {
        const { w, h } = JSON.parse(raw);
        if (typeof w === "number") setWidth(w);
        if (typeof h === "number") setHeight(h);
      }
    } catch {}
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(LS_SIZE, JSON.stringify({ w: width, h: height }));
    } catch {}
  }, [width, height]);

  // Konversation-ID aus/in LocalStorage (Anzeige entfernt)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cid = window.localStorage.getItem(LS_CID);
      if (cid) setConversationId(cid);
    }
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (conversationId) window.localStorage.setItem(LS_CID, conversationId);
    else window.localStorage.removeItem(LS_CID);
  }, [conversationId]);

  // API Ping
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

  // Scroll ans Ende
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open]);

  // Textarea auto-height
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
      const url  = `${apiBase}/v1/chat`;
      const body: any = { question: q, top_k: 5 };
      if (conversationId) body.conversation_id = conversationId;

      // Optimistic user bubble
      setMessages((prev) => [...prev, { role: "user", content: q }]);

      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);

      const answer = (data.answer || "").trim();
      const cites  = (data.citations || []) as Citation[];
      if (data.conversation_id && data.conversation_id !== conversationId) setConversationId(data.conversation_id);

      setMessages((prev) => [...prev, { role: "assistant", content: answer, citations: cites }]);
      setQ("");
      setTimeout(() => taRef.current?.focus(), 0);
    } catch (e: any) {
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

  // Resize-Handler (unten rechts)
  function onResizeStart(e: React.MouseEvent) {
    e.preventDefault();
    resizeState.current = { startX: e.clientX, startY: e.clientY, startW: width, startH: height, active: true };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }
  function onMouseMove(e: MouseEvent) {
    const st = resizeState.current; if (!st || !st.active) return;
    const dx = e.clientX - st.startX;
    const dy = e.clientY - st.startY;
    setWidth(Math.max(320, Math.min(720, st.startW + dx)));
    setHeight(Math.max(360, Math.min(800, st.startH + dy)));
  }
  function onMouseUp() {
    const st = resizeState.current; if (st) st.active = false;
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }

  if (hidden) return null;

  return (
    <>
      {/* Floating Bubble (unten rechts) */}
      <button
        aria-label="AI-Guide öffnen"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed", right: 20, bottom: 20, width: 56, height: 56,
          borderRadius: 999, background: "var(--sl-color-text)", color: "var(--sl-color-bg)",
          border: `1px solid ${COLORS.hairline}`, boxShadow: "0 10px 24px rgba(0,0,0,.18)",
          zIndex: 2147483647, display: "grid", placeItems: "center", cursor: "pointer",
        }}
        title={apiOK === false ? "API nicht erreichbar" : "AI-Guide"}
      >
        <span style={{
          position:"absolute", top:8, right:8, width:8, height:8, borderRadius:99,
          background: apiOK ? "#10b981" : "#ef4444"
        }}/>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11 2a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v6a5 5 0 0 1-5 5h-6a5 5 0 0 1-5-5V9a3 3 0 0 1 3-3h1V5a2 2 0 0 1 2-2h1V2Zm-4 7a1 1 0 1 0 0 2h1a1 1 0 1 0 0-2H7Zm9 0h1a1 1 0 1 1 0 2h-1a1 1 0 1 1 0-2ZM8 14a1 1 0 1 0 0 2h8a1 1 0 1 0 0-2H8Z"/>
        </svg>
      </button>

      {/* Panel (oben links direkt unter Header) */}
      {open && (
        <div
          role="dialog" aria-label="AI-Guide"
          style={{
            position: "fixed",
            left: 16, top: panelTop,
            width, height,
            background: COLORS.bg, color: COLORS.text,
            border: `1px solid ${COLORS.hairline}`,
            borderRadius: 16,
            boxShadow: "0 16px 56px rgba(0,0,0,.22)",
            zIndex: 9999,
            display: "flex", flexDirection: "column", overflow: "hidden",
          }}
        >
          {/* Header */}
          <div style={{
            padding: "10px 12px",
            background: COLORS.bgSoft, color: COLORS.text,
            borderBottom: `1px solid ${COLORS.hairline}`,
            display:"flex", alignItems:"center", gap:8
          }}>
            <strong style={{ fontWeight:700 }}>AI-Guide</strong>
            <span style={{ fontSize:12, opacity:.75 }}>
              {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
            </span>
            <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
              <button
                onClick={resetChat}
                style={{ fontSize:12, padding:"4px 8px", border:`1px solid ${COLORS.hairline}`, borderRadius:8, background: COLORS.bg, color: COLORS.text, cursor:"pointer" }}>
                Reset
              </button>
              <button
                onClick={() => setOpen(false)}
                aria-label="schließen"
                style={{ width:28, height:28, borderRadius:8, border:`1px solid ${COLORS.hairline}`, background: COLORS.bg, color: COLORS.text, cursor:"pointer" }}>
                ✕
              </button>
            </div>
          </div>

          {/* Nachrichten */}
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
                  border: `1px solid ${COLORS.hairline}`,
                  background: m.role === "user" ? "var(--sl-color-text)" : COLORS.bg,
                  color:      m.role === "user" ? "var(--sl-color-bg)"   : COLORS.text,
                  borderRadius: 12,
                  padding: "10px 12px",
                  boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  whiteSpace: "pre-wrap",
                }}>
                  <div style={{ fontSize:12, opacity:.65, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                  {m.content}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div style={{ border: `1px solid ${COLORS.hairline}`, borderRadius: 10, padding: 8, marginTop:6 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4, fontSize:13 }}>Quellen</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {m.citations.map((c)=>(
                        <li key={c.id} style={{ fontSize: 12 }}>
                          {c.title || "(ohne Titel)"}{" "}
                          {typeof c.score === "number" && <span style={{ opacity: .6 }}>· {c.score.toFixed(3)}</span>}
                          {c.url ? (
                            <>
                              {" "}
                              – <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
                            </>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div style={{ padding: 10, borderTop: `1px solid ${COLORS.hairline}`, background: COLORS.bg }}>
            <textarea
              ref={taRef}
              value={q}
              onChange={(e)=>setQ(e.target.value)}
              onInput={autoSizeTA}
              onFocus={autoSizeTA}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                if (e.key === "Escape") setOpen(false);
              }}
              placeholder="Frage stellen… (Enter = senden, Shift+Enter = Zeilenumbruch)"
              rows={1}
              style={{
                width: "100%", padding: 10, borderRadius: 10, resize: "none",
                border: `1px solid ${COLORS.hairline}`,
                lineHeight: "1.4", maxHeight: 180, overflowY: "auto", marginBottom: 8,
                background: COLORS.bg, color: COLORS.text,
              }}
            />
            <div style={{ display:"flex", justifyContent:"space-between" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{
                  padding:"8px 12px", borderRadius:10,
                  border:`1px solid ${COLORS.hairline}`,
                  background:"var(--sl-color-text)", color:"var(--sl-color-bg)",
                  cursor:"pointer"
                }}
              >
                {loading ? "Senden…" : "Senden"}
              </button>
            </div>
          </div>

          {/* Resize-Handle (unten rechts) */}
          <div
            onMouseDown={onResizeStart}
            title="Größe ändern"
            style={{
              position:"absolute", right:6, bottom:6, width:16, height:16, cursor:"nwse-resize",
              borderRight:`2px solid ${COLORS.hairline}`, borderBottom:`2px solid ${COLORS.hairline}`, borderRadius:2,
              opacity:.6
            }}
          />
        </div>
      )}
    </>
  );
}