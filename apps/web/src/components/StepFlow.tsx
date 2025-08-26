import React, { useState } from "react";

export type Step = {
  id: string;
  title: string;
  teaser?: string;
  details?: string;
  href?: string;
};

export default function StepFlow({ steps }: { steps: Step[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <div style={{ maxWidth: 900, margin: "2rem auto" }}>
      <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {steps.map((s, i) => {
          const open = openId === s.id;
          return (
            <li key={s.id} style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 12 }}>
              {/* timeline bar */}
              <div style={{ display: "flex", justifyContent: "center" }}>
                <div style={{ position: "relative" }}>
                  {/* top connector */}
                  {i > 0 && (
                    <div style={{
                      position: "absolute", top: -16, left: 12, width: 4, height: 16, background: "#e5e7eb",
                    }} />
                  )}
                  {/* node */}
                  <div style={{
                    width: 28, height: 28, borderRadius: 20, background: "#111", color: "#fff",
                    display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700
                  }}>{i + 1}</div>
                  {/* bottom connector */}
                  {i < steps.length - 1 && (
                    <div style={{
                      position: "absolute", top: 28, left: 12, width: 4, height: 24, background: "#e5e7eb",
                    }} />
                  )}
                </div>
              </div>

              {/* card */}
              <div style={{
                border: "1px solid #e5e7eb", borderRadius: 12, padding: "12px 14px", marginBottom: 12,
                boxShadow: "0 1px 2px rgba(0,0,0,.04)"
              }}>
                <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
                  <h3 style={{ margin: 0, fontSize: 18 }}>{s.title}</h3>
                  {s.href && (
                    <a href={s.href} style={{ fontSize: 13, opacity: .8, textDecoration: "underline" }}>
                      mehr
                    </a>
                  )}
                  <button
                    onClick={() => setOpenId(open ? null : s.id)}
                    style={{
                      marginLeft: "auto", fontSize: 13, border: "1px solid #ddd", borderRadius: 8,
                      background: "#fff", padding: "4px 8px", cursor: "pointer"
                    }}
                  >
                    {open ? "weniger" : "Details"}
                  </button>
                </div>
                {s.teaser && <p style={{ margin: "6px 0 0 0" }}>{s.teaser}</p>}
                {open && s.details && (
                  <div style={{
                    marginTop: 10, paddingTop: 10, borderTop: "1px dashed #e5e7eb", whiteSpace: "pre-wrap"
                  }}>
                    {s.details}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
