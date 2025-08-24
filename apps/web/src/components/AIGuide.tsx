// apps/web/src/components/AIGuide.tsx
// apps/web/src/components/AIGuide.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

/* ----------------------------- Types ----------------------------- */

type Citation = { id: string; title?: string; url?: string | null; score?: number };

type Meta = {
  top_k: number;
  timing_ms: { embedding: number | null; search: number | null; llm: number | null; total: number | null };
  retrieval: { rank: number; id: string; title?: string; url?: string | null; score?: number; snippet?: string }[];
  backend: { collection: string; embed_backend: string; chat_model: string };
  token_usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
  messages_preview?: { history_sent?: string[]; user?: string } | null;
};

type Msg = { role: "user" | "assistant"; content: string; citations?: Citation[] };

type EventRow = { ts: number; type: "meta" | "token" | "done" | "error" | "info"; data: any };

/* --------------------------- Theme helpers --------------------------- */

function useThemeVars() {
  const get = (v: string, fallback: string) =>
    typeof window !== "undefined"
      ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fallback
      : fallback;

  return {
    bg: get("--sl-color-bg", "#fff"),
    text: get("--sl-color-text", "#111"),
    border: get("--sl-color-gray-5", "#e5e7eb"),
    headerBg: get("--sl-color-gray-6", "#f7f7f8"),
    subtext: get("--sl-color-gray-3", "#6b7280"),
    chipBg: get("--sl-color-gray-6", "#f3f4f6"),
    chipFg: get("--sl-color-text", "#111"),
    primary: get("--sl-color-accent", "#111"),
  };
}

/* --------------------------- Markdown utils -------------------------- */

function renderMarkdown(md: string): string {
  const html = marked.parse(md, { breaks: true }) as string;
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "p",
      "br",
      "strong",
      "em",
      "code",
      "pre",
      "blockquote",
      "ul",
      "ol",
      "li",
      "a",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td"
    ],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
  });
}

/* --------------------------- SSE helper --------------------------- */

function createSSEStream(
  url: string,
  body: any,
  onEvent: (ev: string, data: any) => void,
  signal?: AbortSignal
) {
  const controller = new AbortController();
  const combinedController = new AbortController();

  // Wenn ein externes Signal kommt, auch abbrechen
  if (signal) {
    signal.addEventListener("abort", () => combinedController.abort(), { once: true });
  }
  controller.signal.addEventListener("abort", () => combinedController.abort(), { once: true });

  const promise = (async () => {
    const r = await fetch(url, {
      method: "POST",
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: combinedController.signal,
    });
    if (!r.ok || !r.body) throw new Error(`HTTP ${r.status} ${r.statusText}`);

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // Normalisieren
      buf = buf.replace(/\r\n/g, "\n");
      let idx: number;
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
          try {
            onEvent(ev, JSON.parse(dataStr));
          } catch {
            onEvent(ev, { raw: dataStr });
          }
        }
      }
    }
  })();

  return { controller, promise };
}

/* ---------------------------- UI helpers ---------------------------- */

function Chip({ children }: { children: React.ReactNode }) {
  const t = useThemeVars();
  return (
    <span
      style={{
        fontSize: 12,
        border: `1px solid ${t.border}`,
        borderRadius: 999,
        padding: "4px 10px",
        background: t.chipBg,
        color: t.chipFg,
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  const t = useThemeVars();
  return (
    <div style={{ border: `1px solid ${t.border}`, borderRadius: 10, padding: "10px 12px" }}>
      <div style={{ fontSize: 12, color: t.subtext, marginBottom: 4 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  const t = useThemeVars();
  return <div style={{ fontWeight: 600, color: t.subtext, letterSpacing: 0.2, marginBottom: 6 }}>{children}</div>;
}

/* ============================= Component ============================= */

export default function AIGuide(props: { apiBase?: string }) {
  const t = useThemeVars();

  /* ---- API base ---- */
  const apiBase = useMemo(() => {
    if (props.apiBase && props.apiBase.trim()) return props.apiBase;
    // @ts-ignore: build env replacement
    const envBase = (import.meta as any)?.env?.PUBLIC_API_BASE as string | undefined;
    if (envBase && envBase.trim()) return envBase;
    if (typeof window !== "undefined") {
      return `${window.location.protocol}//${window.location.hostname}:9000`;
    }
    return "http://127.0.0.1:9000";
  }, [props.apiBase]);

  /* ---- State ---- */
  const [apiOK, setApiOK] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [k, setK] = useState(5);
  const [debug, setDebug] = useState(true);
  const [loading, setLoading] = useState(false);

  // Debug artifacts
  const [lastMeta, setLastMeta] = useState<Meta | null>(null);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [activeTab, setActiveTab] = useState<"debug" | "retrieval" | "events" | "analysis" | "all">("debug");

  // scroll
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // autosize
  const MAX_TA_HEIGHT = 200;
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const autoSizeTA = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newH = Math.min(MAX_TA_HEIGHT, el.scrollHeight);
    el.style.height = `${newH}px`;
    el.style.overflowY = el.scrollHeight > newH ? "auto" : "hidden";
  };
  useEffect(autoSizeTA, [q]);

  // reachability
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/ping`);
        if (!live) return;
        setApiOK(r.ok);
      } catch {
        if (!live) return;
        setApiOK(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [apiBase]);

  /* ---- Helpers ---- */

  const addEvent = (type: EventRow["type"], data: any) =>
    setEvents((evs) => [...evs, { ts: Date.now(), type, data }]);

  function resetChat() {
    setMessages([]);
    setLastCitations([]);
    setLastMeta(null);
    setEvents([]);
    setConversationId(null);
  }

  /* ---- Send (SSE + Fallback) ---- */

  async function send() {
    if (!q.trim() || loading || apiOK === false) return;
    setLoading(true);
    setEvents([]);

    // optimistic: user + leerer assistant
    setMessages((prev) => [
      ...prev,
      { role: "user", content: q } as Msg,
      { role: "assistant", content: "" } as Msg,
    ]);
    const assistantIdx = messages.length + 1;

    const body: any = { question: q, top_k: k };
    if (conversationId) body.conversation_id = conversationId;

    const url = debug ? `${apiBase}/v1/chat/stream?debug=1` : `${apiBase}/v1/chat/stream`;
    let gotFirstToken = false;

    const tokenWatch = window.setTimeout(() => {
      if (!gotFirstToken) {
        addEvent("info", "no token within 6s → fallback /v1/chat");
        fallbackRequest();
      }
    }, 6000);

    const { controller, promise } = createSSEStream(
      url,
      body,
      (ev, data) => {
        if (ev === "meta") {
          addEvent("meta", data);
          const meta = (data?.meta || null) as Meta | null;
          setLastMeta(meta);
          const cits = Array.isArray(data?.citations) ? (data.citations as Citation[]) : [];
          setLastCitations(cits);
          if (data?.conversation_id && data.conversation_id !== conversationId) {
            setConversationId(data.conversation_id);
          }
        } else if (ev === "token") {
          gotFirstToken = true;
          addEvent("token", data);
          const delta = typeof data?.delta === "string" ? data.delta : "";
          if (!delta) return;
          setMessages((prev) => {
            const next = prev.slice();
            const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
            if (next[idx] && next[idx].role === "assistant") {
              next[idx] = { ...next[idx], content: (next[idx].content || "") + delta };
            }
            return next;
          });
        } else if (ev === "done") {
          addEvent("done", data);
          const meta = (data?.meta || null) as Meta | null;
          if (meta) setLastMeta(meta);
          setLoading(false);
          window.clearTimeout(tokenWatch);
        }
      }
    );

    async function fallbackRequest() {
      try {
        controller.abort();
      } catch {}
      try {
        const r = await fetch(`${apiBase}/v1/chat${debug ? "?debug=1" : ""}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data?.detail || `${r.status} ${r.statusText}`);

        const answer = (data.answer || "").trim();
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { ...next[idx], content: answer, citations: data.citations || [] };
          }
          return next;
        });
        setLastCitations(data.citations || []);
        setLastMeta(data.meta || null);
        if (data.conversation_id && data.conversation_id !== conversationId) {
          setConversationId(data.conversation_id);
        }
      } catch (e: any) {
        addEvent("error", e?.message || String(e));
        setMessages((prev) => {
          const next = prev.slice();
          const idx = assistantIdx < next.length ? assistantIdx : next.length - 1;
          if (next[idx] && next[idx].role === "assistant") {
            next[idx] = { ...next[idx], content: `⚠ ${e.message || String(e)}` };
          }
          return next;
        });
      } finally {
        setLoading(false);
        window.clearTimeout(tokenWatch);
      }
    }

    try {
      await promise;
    } catch (e: any) {
      addEvent("error", e?.message || String(e));
      await fallbackRequest();
    } finally {
      setQ("");
      setTimeout(() => taRef.current?.focus(), 0);
    }
  }

  /* ---- Derived ---- */

  const waitingOnAssistant =
    loading &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant" &&
    (messages[messages.length - 1].content || "").length === 0;

  /* ------------------------------- UI ------------------------------- */

  return (
    <div style={{ maxWidth: 1200, margin: "1rem auto", padding: "0 0.5rem" }}>
      {/* Header */}
      <div
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 12,
          padding: 12,
          background: t.headerBg,
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <strong>AI-Guide Studio</strong>
        <span style={{ fontSize: 12, color: t.subtext }}>
          {apiOK === null ? "prüfe…" : apiOK ? "verbunden" : "offline"}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: t.subtext }}>
          {conversationId ? `CID ${conversationId.slice(0, 8)}…` : "neu"}
        </span>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} /> Debug
        </label>
        <input
          type="number"
          min={1}
          max={10}
          value={k}
          onChange={(e) => setK(Number(e.target.value))}
          title="top_k"
          style={{ width: 56, padding: "6px 8px", borderRadius: 8, border: `1px solid ${t.border}` }}
        />
        <button
          onClick={resetChat}
          title="Reset conversation"
          style={{
            border: `1px solid ${t.border}`,
            background: t.bg,
            borderRadius: 10,
            padding: "6px 10px",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
      </div>

      {/* Two columns */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Chat pane */}
        <div
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 12,
            padding: 12,
            display: "grid",
            gridTemplateRows: "1fr auto",
            minHeight: 540,
            background: t.bg,
          }}
        >
          {/* Messages */}
          <div style={{ overflow: "auto", display: "grid", gap: 10, paddingRight: 2 }}>
            {messages.map((m, idx) => (
              <div key={idx} style={{ justifySelf: m.role === "user" ? "end" : "start", maxWidth: "100%" }}>
                <div
                  style={{
                    border: `1px solid ${t.border}`,
                    background: m.role === "user" ? t.primary : t.bg,
                    color: m.role === "user" ? "#fff" : t.text,
                    borderRadius: 12,
                    padding: "10px 12px",
                    whiteSpace: "pre-wrap",
                    boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  }}
                >
                  <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>
                    {m.role === "user" ? "Du" : "AI-Guide"}
                  </div>
                  {m.role === "assistant" ? (
                    m.content ? (
                      <div
                        className="ai-md"
                        style={{ lineHeight: 1.5 }}
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                      />
                    ) : (
                      <span style={{ opacity: 0.7, fontSize: 13 }}>Antwort wird generiert…</span>
                    )
                  ) : (
                    m.content
                  )}
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div
                    style={{
                      border: `1px solid ${t.border}`,
                      borderRadius: 10,
                      padding: 10,
                      marginTop: 6,
                      background: t.bg,
                    }}
                  >
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
            {waitingOnAssistant && (
              <div style={{ justifySelf: "start", maxWidth: "100%" }}>
                <div style={{ border: `1px solid ${t.border}`, borderRadius: 12, padding: "10px 12px" }}>
                  <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>AI-Guide</div>
                  <span style={{ opacity: 0.7, fontSize: 13 }}>Antwort wird generiert…</span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div style={{ marginTop: 10 }}>
            <textarea
              ref={taRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onInput={autoSizeTA}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Frage stellen… (Enter = senden, Shift+Enter = Zeilenumbruch)"
              rows={1}
              style={{
                width: "100%",
                padding: 10,
                borderRadius: 10,
                border: `1px solid ${t.border}`,
                background: t.bg,
                color: t.text,
                resize: "none",
                lineHeight: "1.5",
                maxHeight: MAX_TA_HEIGHT,
                overflowY: "auto",
                marginBottom: 8,
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={send}
                disabled={loading || !q.trim() || apiOK === false}
                style={{
                  border: "1px solid #333",
                  background: "#111",
                  color: "#fff",
                  borderRadius: 10,
                  padding: "8px 12px",
                  cursor: "pointer",
                }}
              >
                {loading ? "Senden…" : "Senden"}
              </button>
            </div>
          </div>
        </div>

        {/* Analysis pane */}
        <div
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 12,
            padding: 12,
            background: t.headerBg,
          }}
        >
          {/* Tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
            {(["debug", "retrieval", "events", "analysis", "all"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  border: `1px solid ${activeTab === tab ? "#111" : t.border}`,
                  background: activeTab === tab ? "#111" : t.bg,
                  color: activeTab === tab ? "#fff" : t.text,
                  borderRadius: 10,
                  padding: "6px 10px",
                  cursor: "pointer",
                  textTransform: "uppercase",
                  fontSize: 12,
                  letterSpacing: 0.3,
                }}
              >
                {tab.toUpperCase()}
              </button>
            ))}
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button
                onClick={() =>
                  navigator.clipboard
                    .writeText(JSON.stringify({ meta: lastMeta, citations: lastCitations, events }, null, 2))
                    .catch(() => {})
                }
                style={{
                  border: `1px solid ${t.border}`,
                  background: t.bg,
                  color: t.text,
                  borderRadius: 10,
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                Copy JSON
              </button>
              <button
                onClick={() => {
                  const all = composeALL(messages, lastCitations, lastMeta, events);
                  navigator.clipboard.writeText(all).catch(() => {});
                }}
                style={{
                  border: `1px solid ${t.border}`,
                  background: t.bg,
                  color: t.text,
                  borderRadius: 10,
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                Copy ALL
              </button>
            </div>
          </div>

          {/* Tab content */}
          {activeTab === "debug" && (
            <div style={{ display: "grid", gap: 12 }}>
              <SectionTitle>Timings</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(140px, 1fr))", gap: 10 }}>
                <Stat label="Embedding" value={`${lastMeta?.timing_ms.embedding ?? "-"} ms`} />
                <Stat label="Search" value={`${lastMeta?.timing_ms.search ?? "-"} ms`} />
                <Stat label="LLM" value={`${lastMeta?.timing_ms.llm ?? "-"} ms`} />
                <Stat label="Total" value={`${lastMeta?.timing_ms.total ?? "-"} ms`} />
              </div>
              <SectionTitle>Backend</SectionTitle>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {lastMeta?.backend?.collection && (
                  <Chip>
                    Collection: <strong>{lastMeta.backend.collection}</strong>
                  </Chip>
                )}
                {lastMeta?.backend?.embed_backend && (
                  <Chip>
                    Embed: <strong>{lastMeta.backend.embed_backend}</strong>
                  </Chip>
                )}
                {lastMeta?.backend?.chat_model && (
                  <Chip>
                    Model: <strong>{lastMeta.backend.chat_model}</strong>
                  </Chip>
                )}
                {lastMeta?.token_usage && (
                  <Chip>Tokens: {lastMeta.token_usage.total_tokens ?? "-"}</Chip>
                )}
                {lastMeta?.messages_preview?.history_sent && lastMeta.messages_preview.history_sent.length > 0 && (
                  <Chip>History: {lastMeta.messages_preview.history_sent.join(" → ")}</Chip>
                )}
              </div>

              <SectionTitle>Citations</SectionTitle>
              <ul style={{ margin: 0, paddingLeft: 18, opacity: 0.9 }}>
                {lastCitations.length === 0 && <li style={{ opacity: 0.6 }}>–</li>}
                {lastCitations.map((c) => (
                  <li key={c.id} style={{ fontSize: 13 }}>
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

          {activeTab === "retrieval" && (
            <div style={{ display: "grid", gap: 10 }}>
              <SectionTitle>Retrieval</SectionTitle>
              {lastMeta?.retrieval?.map((r) => (
                <div key={`${r.rank}-${r.id}`} style={{ border: `1px solid ${t.border}`, borderRadius: 10, padding: 10 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                    <span style={{ fontSize: 12, opacity: 0.7 }}>#{r.rank}</span>
                    <strong>{r.title || "(ohne Titel)"} </strong>
                    {typeof r.score === "number" && (
                      <span style={{ fontSize: 12, opacity: 0.7 }}>score {r.score.toFixed(3)}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4, wordBreak: "break-all" }}>
                    id {r.id}
                    {r.url ? (
                      <>
                        {" "}
                        ·{" "}
                        <a href={r.url} target="_blank" rel="noreferrer">
                          {r.url}
                        </a>
                      </>
                    ) : null}
                  </div>
                  {r.snippet && <div style={{ marginTop: 8, whiteSpace: "pre-wrap", fontSize: 13 }}>{r.snippet}</div>}
                </div>
              ))}
              {!lastMeta?.retrieval?.length && <div style={{ opacity: 0.6 }}>–</div>}
            </div>
          )}

          {activeTab === "events" && (
            <div style={{ display: "grid", gap: 8 }}>
              <SectionTitle>SSE Events</SectionTitle>
              <div
                style={{
                  border: `1px solid ${t.border}`,
                  borderRadius: 10,
                  background: t.bg,
                  padding: 10,
                  maxHeight: 360,
                  overflow: "auto",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 12,
                  whiteSpace: "pre-wrap",
                }}
              >
                {events.length === 0 ? (
                  <span style={{ opacity: 0.6 }}>–</span>
                ) : (
                  events.map((e, i) => (
                    <div key={i} style={{ marginBottom: 6 }}>
                      <span style={{ opacity: 0.65 }}>
                        {new Date(e.ts).toLocaleTimeString()} {e.type.toUpperCase()}{" "}
                      </span>
                      {typeof e.data === "string" ? e.data : JSON.stringify(e.data)}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === "analysis" && (
            <div style={{ display: "grid", gap: 8 }}>
              <SectionTitle>Analysis JSON</SectionTitle>
              <pre
                style={{
                  border: `1px solid ${t.border}`,
                  borderRadius: 10,
                  background: t.bg,
                  padding: 10,
                  maxHeight: 480,
                  overflow: "auto",
                  fontSize: 12,
                }}
              >
                {JSON.stringify({ meta: lastMeta, citations: lastCitations, events }, null, 2)}
              </pre>
            </div>
          )}

          {activeTab === "all" && (
            <div style={{ display: "grid", gap: 8 }}>
              <SectionTitle>ALL (kopierbar)</SectionTitle>
              <textarea
                readOnly
                value={composeALL(messages, lastCitations, lastMeta, events)}
                style={{
                  width: "100%",
                  minHeight: 520,
                  border: `1px solid ${t.border}`,
                  borderRadius: 10,
                  padding: 10,
                  background: t.bg,
                  color: t.text,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 12,
                  lineHeight: 1.5,
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------- Compose ALL text -------------------------- */

function composeALL(msgs: Msg[], citations: Citation[], meta: Meta | null, events: EventRow[]) {
  const lines: string[] = [];
  lines.push("# Conversation");
  msgs.forEach((m) => {
    lines.push(`\n## ${m.role.toUpperCase()}\n`);
    lines.push(m.content || "");
  });

  lines.push("\n\n# Citations");
  if (!citations?.length) {
    lines.push("(none)");
  } else {
    citations.forEach((c, i) =>
      lines.push(
        `- [${i + 1}] ${c.title || "(ohne Titel)"}${typeof c.score === "number" ? ` · ${c.score.toFixed(3)}` : ""}${
          c.url ? ` – ${c.url}` : ""
        }`
      )
    );
  }

  lines.push("\n\n# Meta");
  lines.push(JSON.stringify(meta || {}, null, 2));

  lines.push("\n\n# Events");
  events.forEach((e) => lines.push(`${new Date(e.ts).toISOString()} ${e.type.toUpperCase()} ${jsonStr(e.data)}`));

  return lines.join("\n");
}

function jsonStr(x: any) {
  try {
    return typeof x === "string" ? x : JSON.stringify(x);
  } catch {
    return String(x);
  }
}