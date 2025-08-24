// apps/web/src/components/ChatWidget.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

type Citation = { id: string; title?: string; url?: string | null; score?: number };
type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

const LS_KEY_CID = "aiGuide.convId.v1";
const LS_KEY_SIZE = "aiGuide.panelSize.v1";

/** Minimaler SVG-Spinner */
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

/** Farbtokens aus Starlight (Dark/Light) */
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
    btnBg:    get("--sl-color-bg-nav", "#fff"),
    btnBorder:get("--sl-color-gray-4", "#d1d5db"),
  };
}

/** sicheres Markdown */
function renderMarkdown(md: string): string {
  const html = marked.parse(md, { breaks: true }) as string;
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "p","br","strong","em","code","pre","blockquote",
      "ul","ol","li","a","h1","h2","h3","h4","h5","h6"
    ],
    ALLOWED_ATTR: ["href","target","rel","class"],
  });
}

/** SSE-Client mit Fallback: echte SSE → streamen; JSON-Array → komplett lesen & nachspielen */
function createSSEStream(
  url: string,
  body: any,
  onEvent: (ev: string, data: any) => void
) {
  const controller = new AbortController();

  const promise = (async () => {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Accept": "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status} ${r.statusText}`);

    const ct = (r.headers.get("content-type") || "").toLowerCase();

    // Fallback: Server liefert JSON-Array (historischer Bug)
    if (!ct.includes("text/event-stream")) {
      const text = await r.text();
      try {
        const arr = JSON.parse(text);
        if (Array.isArray(arr)) {
          for (const s of arr) {
            if (typeof s !== "string") continue;
            // ein Eintrag entspricht einem kompletten SSE-Block
            const block = s.replace(/\r\n/g, "\n").trimEnd();
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
          // sicherstellen, dass UI beendet
          onEvent("done", {});
          return;
        }
      } catch {
        // fällt unten in den normalen Parser zurück (wird dann nichts finden)
      }
      throw new Error("Unerwartetes Antwortformat (kein event-stream und kein JSON-Array).");
    }

    // ECHTES SSE: stream-parsen
    if (!r.body) throw new Error("Fehlender Response-Body");
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // CRLF -> LF normalisieren, dann Blöcke trennen
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

    // Falls kein "done" kam, trotzdem abschließen
    onEvent("done", {});
  })();

  return { controller, promise };
}

export default function ChatWidget(props: { apiBase?: string; suppressOnGuide?: boolean }) {
  const theme = useThemeVars();

  // ggf. auf /guide unterdrücken
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (props.suppressOnGuide === false) return;
    if (typeof window !== "undefined") setHidden(window.location.pathname.startsWith("/guide"));
  }, [props.suppressOnGuide]);
  if (hidden) return null;

  // API-Basis
  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore build env
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:9000`;
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  // State
  const [open, setOpen] = useState(false);
  const [apiOK, setApiOK] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  // Panel-Size (persist)
  const [{ w, h }, setSize] = useState(() => {
    if (typeof window !== "undefined") {
      const raw = window.localStorage.getItem(LS_KEY_SIZE);
      if (raw) { try { return JSON.parse(raw); } catch {} }
    }
    return { w: 420, h: 520 };
  });
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(LS_KEY_SIZE, JSON.stringify({ w, h }));
    }
  }, [w, h]);

  // Conv-ID persist
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cid = window.localStorage.getItem(LS_KEY_CID);
      if (cid) setConversationId(cid);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (conversationId) window.localStorage.setItem(LS_KEY_CID, conversationId);
      else window.localStorage.removeItem(LS_KEY_CID);
    }
  }, [conversationId]);

  // API ping
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

  // Scroll
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open]);

  // Textarea autosize
  const MAX_TA_HEIGHT = 180;
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const autoSizeTA = () => {
    const el = taRef.current; if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q, open]);

  // Resize-Griff (oben links)
  const resizingRef = useRef<null | { startX: number; startY: number; startW: number; startH: number }>(null);
  function onResizeDown(e: React.MouseEvent) {
    e.preventDefault();
    resizingRef.current = { startX: e.clientX, startY: e.clientY, startW: w, startH: h };
    window.addEventListener("mousemove", onResizeMove);
    window.addEventListener("mouseup", onResizeUp);
  }
  function onResizeMove(e: MouseEvent) {
    const st = resizingRef.current; if (!st) return;
    const dx = st.startX - e.clientX;
    const dy = st.startY - e.clientY;
    const nw = Math.min(Math.max(320, st.startW + dx), Math.min(640, window.innerWidth - 24));
    const nh = Math.min(Math.max(300, st.startH + dy), Math.min(800, window.innerHeight - 140));
    setSize({ w: nw, h: nh });
  }
  function onResizeUp() {
    resizingRef.current = null;
    window.removeEventListener("mousemove", onResizeMove);
    window.removeEventListener("mouseup", onResizeUp);
  }

  async function send() {
    if (!q.trim() || loading || apiOK === false) return;
    setLoading(true);

    // optimistic: user + leere assistant-Bubble
    setMessages((prev) => [...prev, { role: "user", content: q }, { role: "assistant", content: "" }]);
    const assistantIdx = messages.length + 1; // Index der neu angehängten Assistant-Bubble

    const body: any = { question: q, top_k: 5 };
    if (conversationId) body.conversation_id = conversationId;

    const streamURL = `${apiBase}/v1/chat/stream`;

    // Watchdogs
    let gotFirstToken = false;
    let finished = false;
    const tokenTimeout = window.setTimeout(() => {
      if (!gotFirstToken) abortAndFallback();
    }, 6000);
    const hardTimeout = window.setTimeout(() => {
      if (!finished) {
        // als letzte Rückfallebene abbrechen und Fallback nutzen
        abortAndFallback();
      }
    }, 30000);

    const { controller, promise } = createSSEStream(streamURL, body, (ev, data) => {
      if (ev === "meta") {
        gotFirstToken = true; // meta kam → Verbindung lebt
        if (data?.conversation_id && data.conversation_id !== conversationId) {
          setConversationId(data.conversation_id);
        }
        if (Array.isArray(data?.citations) && data.citations.length > 0) {
          setMessages((prev) => {
            const next = prev.slice();
            const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
            if (next[idx] && next[idx].role === "assistant") {
              next[idx] = { ...next[idx], citations: data.citations as Citation[] };
            }
            return next;
          });
        }
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
        finished = true;
        window.clearTimeout(tokenTimeout);
        window.clearTimeout(hardTimeout);
        setLoading(false);
      }
    });

    async function abortAndFallback() {
      try { controller.abort(); } catch {}
      try {
        const r = await fetch(`${apiBase}/v1/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);
        const answer = (data.answer || "").trim();
        const citations = (data.citations || []) as Citation[];
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { role: "assistant", content: answer, citations };
          }
          return next;
        });
        if (data.conversation_id && data.conversation_id !== conversationId) {
          setConversationId(data.conversation_id);
        }
      } catch (e2: any) {
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { role: "assistant", content: `⚠ ${e2.message || String(e2)}` };
          }
          return next;
        });
      } finally {
        finished = true;
        window.clearTimeout(tokenTimeout);
        window.clearTimeout(hardTimeout);
        setLoading(false);
      }
    }

    try {
      await promise; // wartet bis Stream endet
    } catch {
      // Netz-/Streamfehler → Fallback
      await abortAndFallback();
    } finally {
      setQ("");
      setTimeout(() => taRef.current?.focus(), 0);
    }
  }

  function resetChat() {
    setMessages([]);
    setConversationId(null);
    setQ("");
  }

  return (
    <>
      {/* Bubble unten rechts */}
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
          zIndex: 2147483647,
          display: "grid", placeItems: "center",
          cursor: "pointer",
        }}
        title={apiOK === false ? "API nicht erreichbar" : "AI-Guide"}
      >
        <span style={{
          position:"absolute", top:8, right:8, width:8, height:8, borderRadius:99,
          background: apiOK ? "#0a7" : "#b00020"
        }} />
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
            width: `min(${w}px, 94vw)`,
            height: `min(${h}px, 80vh)`,
            background: theme.bg,
            color: theme.text,
            border: `1px solid ${theme.border}`,
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
            onMouseDown={onResizeDown}
            title="Größe ändern"
            style={{
              position: "absolute",
              left: 8, top: 8,
              width: 16, height: 16,
              borderLeft: `2px solid ${theme.border}`,
              borderTop: `2px solid ${theme.border}`,
              borderRadius: 4,
              cursor: "nwse-resize",
              opacity: .9,
            }}
          />

          {/* Header */}
          <div style={{
            padding: "10px 12px",
            borderBottom: `1px solid ${theme.border}`,
            background: theme.headerBg,
            display:"flex", alignItems:"center", gap:10
          }}>
            <strong style={{ fontWeight:700 }}>AI-Guide</strong>
            <span style={{ fontSize:12, opacity:.75 }}>
              {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
            </span>
            {loading && (
              <span title="Antwort wird generiert…" style={{ display:"inline-flex", alignItems:"center", gap:6 }}>
                <Spinner size={16} color={theme.text} />
              </span>
            )}
            <button onClick={resetChat}
              style={{
                marginLeft:"auto",
                fontSize:12, padding:"4px 8px",
                border:`1px solid ${theme.btnBorder}`,
                borderRadius:8, background: theme.btnBg, cursor:"pointer"
              }}>
              Reset
            </button>
            <button onClick={() => setOpen(false)}
              aria-label="schließen"
              style={{
                marginLeft:8, width:28, height:28, borderRadius:8,
                border:`1px solid ${theme.btnBorder}`, background: theme.btnBg, cursor:"pointer"
              }}>
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
                  border: `1px solid ${theme.border}`,
                  background: m.role === "user" ? "#111" : theme.bg,
                  color: m.role === "user" ? "#fff" : theme.text,
                  borderRadius: 12,
                  padding: "10px 12px",
                  boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  whiteSpace: "pre-wrap",
                }}>
                  <div style={{ fontSize:12, opacity:.65, marginBottom:4 }}>{m.role === "user" ? "Du" : "AI-Guide"}</div>
                  {m.role === "assistant"
                    ? (m.content
                        ? <div className="ai-md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} style={{ lineHeight: 1.5 }} />
                        : (
                          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                            <Spinner size={16} color={theme.text} />
                            <span style={{ opacity:.7, fontSize:13 }}>Antwort wird generiert…</span>
                          </div>
                        )
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
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div style={{ padding: 10, borderTop: `1px solid ${theme.border}` }}>
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
                border: `1px solid ${theme.border}`,
                resize: "none",
                lineHeight: "1.4",
                maxHeight: 180,
                overflowY: "auto",
                marginBottom: 8,
                background: theme.bg, color: theme.text,
              }}
            />
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{
                  padding:"8px 12px",
                  borderRadius:10,
                  border:"1px solid #333",
                  background:"#111",
                  color:"#fff",
                  cursor:"pointer",
                  display:"inline-flex",
                  alignItems:"center",
                  gap:8
                }}
              >
                {loading ? (<><Spinner size={16} color="#fff" /> <span>Senden…</span></>) : "Senden"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}