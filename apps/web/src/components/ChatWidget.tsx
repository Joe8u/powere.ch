// apps/web/src/components/ChatWidget.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

const LS_CID  = "aiGuide.convId.v1";
const LS_SIZE = "aiGuide.widget.size.v1";

export default function ChatWidget(props: { apiBase?: string; suppressOnGuide?: boolean }) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  // API & Chat
  const [apiOK, setApiOK] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  // Panelgröße (persistiert) – unten rechts verankert
  const [width, setWidth] = useState<number>(380);
  const [height, setHeight] = useState<number>(520);

  const taRef  = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const resizeState = useRef<{ startX: number; startY: number; startW: number; startH: number; active: boolean } | null>(null);

  // Starlight-Farben (funktionieren in dark/light)
  const COLORS = {
    bg:       "var(--sl-color-bg)",
    bgSoft:   "var(--sl-color-bg-soft)",
    text:     "var(--sl-color-text)",
    hairline: "var(--sl-color-hairline)",
  } as const;

  // Bubble auf /guide optional ausblenden
  useEffect(() => {
    if (props.suppressOnGuide === false) return;
    if (typeof window !== "undefined") setHidden(window.location.pathname.startsWith("/guide"));
  }, [props.suppressOnGuide]);

  // API-Basis
  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore – PUBLIC_ Variablen werden beim Build ersetzt
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:9000`;
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // Größe laden/speichern
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
    try { window.localStorage.setItem(LS_SIZE, JSON.stringify({ w: width, h: height })); } catch {}
  }, [width, height]);

  // Konversation-ID (Anzeige entfernt, aber für Verlauf behalten)
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

      // optimistic
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

  // Resize-Handler (GRIFF OBEN LINKS; Panel unten-rechts bleibt fix)
  function onResizeStart(e: React.MouseEvent<HTMLDivElement>) {
    e.preventDefault();
    resizeState.current = { startX: e.clientX, startY: e.clientY, startW: width, startH: height, active: true };
    const onMove = (ev: MouseEvent) => {
      if (!resizeState.current?.active) return;
      const dx = ev.clientX - resizeState.current.startX; // >0 wenn Maus nach rechts
      const dy = ev.clientY - resizeState.current.startY; // >0 wenn Maus nach unten
      // Griff oben links: wenn Maus nach rechts/unten bewegt, wird Panel kleiner
      const newW = clamp(resizeState.current.startW - dx, 300, 800);
      const newH = clamp(resizeState.current.startH - dy, 360, 900);
      setWidth(newW);
      setHeight(newH);
    };
    const onUp = () => {
      resizeState.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  if (hidden) return null;

  return (
    <>
      {/* Floating bubble – UNTEN RECHTS */}
      <button
        aria-label="AI-Guide öffnen"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          right: 20, bottom: 20,
          width: 56, height: 56,
          borderRadius: 999,
          background: "var(--sl-color-accent)",
          color: "white",
          border: "1px solid var(--sl-color-hairline)",
          boxShadow: "0 10px 24px rgba(0,0,0,.18)",
          zIndex: 2147483647,
          display: "grid", placeItems: "center",
          cursor: "pointer",
        }}
        title={apiOK === false ? "API nicht erreichbar" : "AI-Guide"}
      >
        {/* Status-Punkt */}
        <span style={{
          position:"absolute", top:8, right:8, width:8, height:8, borderRadius:99,
          background: apiOK ? "#12b886" : "#d33"
        }} />
        {/* Robot-Icon */}
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11 2a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v6a5 5 0 0 1-5 5h-6a5 5 0 0 1-5-5V9a3 3 0 0 1 3-3h1V5a2 2 0 0 1 2-2h1V2Zm-4 7a1 1 0 1 0 0 2h1a1 1 0 1 0 0-2H7Zm9 0h1a1 1 0 1 1 0 2h-1a1 1 0 1 1 0-2ZM8 14a1 1 0 1 0 0 2h8a1 1 0 1 0 0-2H8Z"/>
        </svg>
      </button>

      {/* Panel – UNTEN RECHTS; Resize-Griff OBEN LINKS */}
      {open && (
        <div
          role="dialog"
          aria-label="AI-Guide"
          style={{
            position: "fixed",
            right: 16, bottom: 84,
            width, height,
            background: COLORS.bg,
            color: COLORS.text,
            border: `1px solid ${COLORS.hairline}`,
            borderRadius: 16,
            boxShadow: "0 16px 56px rgba(0,0,0,.22)",
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Resize-Griff oben links */}
          <div
            onMouseDown={onResizeStart}
            title="Größe ändern"
            style={{
              position:"absolute", top:8, left:8, width:16, height:16,
              borderTop: `2px solid ${COLORS.hairline}`,
              borderLeft:`2px solid ${COLORS.hairline}`,
              borderTopLeftRadius: 4,
              cursor:"nwse-resize",
              zIndex: 2,
            }}
          />

          {/* Header */}
          <div style={{
            padding: "10px 12px",
            borderBottom: `1px solid ${COLORS.hairline}`,
            background: COLORS.bgSoft,
            display:"flex", alignItems:"center", gap:10
          }}>
            <strong style={{ fontWeight:700 }}>AI-Guide</strong>
            <span style={{ fontSize:12, opacity:.8, display:"inline-flex", alignItems:"center", gap:6 }}>
              <span style={{
                width:8, height:8, borderRadius:99,
                background: apiOK ? "#12b886" : "#d33"
              }} />
              {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
            </span>
            <button onClick={resetChat}
              style={{ marginLeft:"auto", fontSize:12, padding:"4px 8px", border:`1px solid ${COLORS.hairline}`, borderRadius:8, background:"transparent", cursor:"pointer" }}>
              Reset
            </button>
            <button onClick={() => setOpen(false)}
              aria-label="schließen"
              style={{ marginLeft:8, width:28, height:28, borderRadius:8, border:`1px solid ${COLORS.hairline}`, background:"transparent", cursor:"pointer" }}>
              ✕
            </button>
          </div>

          {/* Messages */}
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
                  background: m.role === "user" ? "var(--sl-color-accent)" : COLORS.bg,
                  color: m.role === "user" ? "white" : COLORS.text,
                  borderRadius: 12,
                  padding: "10px 12px",
                  boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  whiteSpace: "pre-wrap",
                }}>
                  <div style={{ fontSize:12, opacity:.75, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                  {m.content}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div style={{ border: `1px solid ${COLORS.hairline}`, borderRadius: 10, padding: 8, marginTop:6 }}>
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

          {/* Input */}
          <div style={{ padding: 10, borderTop: `1px solid ${COLORS.hairline}`, background: COLORS.bg }}>
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
                border: `1px solid ${COLORS.hairline}`,
                resize: "none",
                lineHeight: "1.4",
                maxHeight: MAX_TA_HEIGHT,
                overflowY: "auto",
                marginBottom: 8,
                background: COLORS.bg,
                color: COLORS.text,
              }}
            />
            <div style={{ display:"flex", gap:8, justifyContent:"space-between", alignItems:"center" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{
                  padding:"8px 12px",
                  borderRadius:10,
                  border:`1px solid ${COLORS.hairline}`,
                  background:"var(--sl-color-accent)",
                  color:"white",
                  cursor:"pointer"
                }}
              >
                {loading ? "Senden…" : "Senden"}
              </button>
              <span style={{ fontSize: 11, opacity:.6 }}>
                {apiOK === false ? "API offline" : " "}
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}