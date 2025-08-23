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

const LS_CONV = "aiGuide.convId.v1";
const LS_SIZE = "aiGuide.size.v1";

export default function ChatWidget(props: { apiBase?: string; suppressOnGuide?: boolean }) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  // Farben über Starlight-Design-Tokens (mit Fallbacks)
  const PANEL_BG   = "var(--sl-color-bg, #ffffff)";
  const PANEL_FG   = "var(--sl-color-text, #111111)";
  const HEADER_BG  = "var(--sl-color-bg-soft, #f7f7f8)";
  const BORDER     = "var(--sl-color-gray-5, #e5e7eb)";
  const BTN_BORDER = "var(--sl-color-gray-6, #999)";
  const BUBBLE_BG  = "var(--sl-color-accent, #111)";
  const BUBBLE_FG  = "var(--sl-color-accent-text, #fff)";
  const POSITIVE   = "var(--sl-color-green, #0a7)";
  const NEGATIVE   = "var(--sl-color-red, #b00020)";

  // Standard: auf /guide verstecken – außer suppressOnGuide === false
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

  // Panel-Ref + (optionale) persistent sizes
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelW, setPanelW] = useState<number | null>(null);
  const [panelH, setPanelH] = useState<number | null>(null);

  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  // Conv-ID persistieren
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cid = window.localStorage.getItem(LS_CONV);
      if (cid) setConversationId(cid);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (conversationId) window.localStorage.setItem(LS_CONV, conversationId);
      else window.localStorage.removeItem(LS_CONV);
    }
  }, [conversationId]);

  // Größe laden & clampen
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(LS_SIZE);
      if (!raw) return;
      const { w, h } = JSON.parse(raw) as { w: number; h: number };
      const maxW = Math.floor(window.innerWidth * 0.92);
      const maxH = Math.floor(window.innerHeight * 0.90);
      const clampedW = Math.max(320, Math.min(maxW, w));
      const clampedH = Math.max(280, Math.min(maxH, h));
      setPanelW(clampedW);
      setPanelH(clampedH);
    } catch { /* ignore */ }
  }, []);

  // Änderungen der Größe speichern (wenn user resized)
  useEffect(() => {
    if (!open || !panelRef.current || typeof ResizeObserver === "undefined") return;
    const el = panelRef.current;
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (!e) return;
      const box = e.borderBoxSize?.[0];
      // Fallback auf getBoundingClientRect, falls borderBoxSize fehlt
      const rect = el.getBoundingClientRect();
      const w = Math.round(box?.inlineSize ?? rect.width);
      const h = Math.round(box?.blockSize ?? rect.height);
      // Nur speichern, nicht zwingend State updaten (verhindert Re-Render beim Drag)
      try { window.localStorage.setItem(LS_SIZE, JSON.stringify({ w, h })); } catch {}
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

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

  // Auto-Scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open]);

  // Auto-Resize Textarea (ChatGPT-like)
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

      // Optimistic UI
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

  if (hidden) return null;

  return (
    <>
      {/* Floating bubble */}
      <button
        aria-label="AI-Guide öffnen"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          right: 20,
          bottom: 20,
          width: 56,
          height: 56,
          borderRadius: 999,
          background: BUBBLE_BG,
          color: BUBBLE_FG,
          border: "1px solid rgba(0,0,0,.25)",
          boxShadow: "0 10px 24px rgba(0,0,0,.18)",
          zIndex: 2147483647,
          display: "grid",
          placeItems: "center",
          cursor: "pointer",
        }}
        title={apiOK === false ? "API nicht erreichbar" : "AI-Guide"}
      >
        {/* Status-Dot */}
        <span
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            width: 8,
            height: 8,
            borderRadius: 99,
            background: apiOK ? POSITIVE : NEGATIVE,
          }}
        />
        {/* Robot-Icon */}
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11 2a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v6a5 5 0 0 1-5 5h-6a5 5 0 0 1-5-5V9a3 3 0 0 1 3-3h1V5a2 2 0 0 1 2-2h1V2Zm-4 7a1 1 0 1 0 0 2h1a1 1 0 1 0 0-2H7Zm9 0h1a1 1 0 1 1 0 2h-1a1 1 0 1 1 0-2ZM8 14a1 1 0 1 0 0 2h8a1 1 0 1 0 0-2H8Z" />
        </svg>
      </button>

      {/* Panel */}
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="AI-Guide"
          style={{
            position: "fixed",
            right: 16,
            bottom: 84,
            width: panelW ? `${panelW}px` : "min(420px, 92vw)",
            height: panelH ? `${panelH}px` : "min(70vh, 600px)",
            minWidth: 320,
            minHeight: 280,
            maxWidth: "92vw",
            maxHeight: "90vh",
            resize: "both",            // <- Drag zum Vergrößern/Verkleinern
            background: PANEL_BG,
            color: PANEL_FG,
            border: `1px solid ${BORDER}`,
            borderRadius: 16,
            boxShadow: "0 16px 56px rgba(0,0,0,.22)",
            zIndex: 2147483647,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",        // resize benötigt overflow != visible
          }}
        >
          {/* sichtbarer Resize-Griff (rein visuell) */}
          <div
            aria-hidden
            style={{
              position: "absolute",
              right: 6,
              bottom: 6,
              width: 16,
              height: 16,
              pointerEvents: "none",
              background:
                `linear-gradient(135deg, transparent 0 6px, ${BORDER} 6px 7px, transparent 7px 10px, ${BORDER} 10px 11px, transparent 11px)`,
              opacity: 0.8,
              borderBottomRightRadius: 14,
            }}
          />

          {/* Header */}
          <div
            style={{
              padding: "10px 12px",
              background: HEADER_BG,
              borderBottom: `1px solid ${BORDER}`,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <strong style={{ fontWeight: 700 }}>AI-Guide</strong>
            <span style={{ fontSize: 12, opacity: 0.7 }}>
              {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
            </span>
            <span style={{ marginLeft: "auto", fontSize: 11, opacity: 0.65 }}>
              {conversationId ? `Conv ${conversationId.slice(0, 8)}…` : "neue Unterhaltung"}
            </span>
            <button
              onClick={resetChat}
              style={{
                marginLeft: 8,
                fontSize: 12,
                fontWeight: 600,
                padding: "6px 10px",
                border: `1px solid ${BTN_BORDER}`,
                borderRadius: 8,
                background: "var(--sl-color-bg, #fff)",
                color: PANEL_FG,
                cursor: "pointer",
              }}
              title="Unterhaltung zurücksetzen"
            >
              ↺ Reset
            </button>
            <button
              onClick={() => setOpen(false)}
              aria-label="schließen"
              title="Schließen"
              style={{
                marginLeft: 8,
                width: 32,
                height: 32,
                borderRadius: 8,
                border: `1px solid ${BTN_BORDER}`,
                background: "var(--sl-color-bg, #fff)",
                color: PANEL_FG,
                fontSize: 18,
                lineHeight: "30px",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflow: "auto", padding: 12, display: "grid", gap: 10 }}>
            {messages.length === 0 && (
              <div style={{ fontSize: 13, opacity: 0.75 }}>
                Hallo! Stell mir eine Frage zu powere.ch, Daten, Loaders oder Methodik.
                <br />
                Tipp: <span style={{ fontFamily: "monospace" }}>Shift+Enter</span> → neue Zeile,{" "}
                <span style={{ fontFamily: "monospace" }}>Enter</span> → senden.
              </div>
            )}
            {messages.map((m, idx) => (
              <div key={idx} style={{ justifySelf: m.role === "user" ? "end" : "start", maxWidth: "100%" }}>
                <div
                  style={{
                    border: `1px solid ${BORDER}`,
                    background: m.role === "user" ? "var(--sl-color-accent, #111)" : PANEL_BG,
                    color: m.role === "user" ? "var(--sl-color-accent-text, #fff)" : PANEL_FG,
                    borderRadius: 12,
                    padding: "10px 12px",
                    boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  <div style={{ fontSize: 12, opacity: 0.65, marginBottom: 4 }}>
                    {m.role === "user" ? "Du" : "AI-Guide"}
                  </div>
                  {m.content}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div style={{ border: `1px solid ${BORDER}`, borderRadius: 10, padding: 8, marginTop: 6 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>Quellen</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {m.citations.map((c) => (
                        <li key={c.id} style={{ fontSize: 12 }}>
                          {c.title || "(ohne Titel)"}{" "}
                          {typeof c.score === "number" && <span style={{ opacity: 0.6 }}>· {c.score.toFixed(3)}</span>}
                          {c.url && (
                            <>
                              {" "}
                              –{" "}
                              <a href={c.url} target="_blank" rel="noreferrer">
                                {c.url}
                              </a>
                            </>
                          )}
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
          <div style={{ padding: 10, borderTop: `1px solid ${BORDER}`, background: PANEL_BG }}>
            <textarea
              ref={taRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
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
                border: `1px solid ${BORDER}`,
                background: "var(--sl-color-bg, #fff)",
                color: PANEL_FG,
                resize: "none",
                lineHeight: "1.4",
                maxHeight: MAX_TA_HEIGHT,
                overflowY: "auto",
                marginBottom: 8,
              }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{
                  padding: "8px 12px",
                  borderRadius: 10,
                  border: "1px solid rgba(0,0,0,.35)",
                  background: "var(--sl-color-accent, #111)",
                  color: "var(--sl-color-accent-text, #fff)",
                  cursor: "pointer",
                }}
              >
                {loading ? "Senden…" : "Senden"}
              </button>
              <span style={{ fontSize: 11, opacity: 0.6 }}>
                {apiOK === false ? "API offline" : conversationId ? `Conv ${conversationId.slice(0, 8)}…` : "neu"}
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}