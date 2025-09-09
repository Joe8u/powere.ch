// apps/web/src/components/dashboard/ui/KpiCard.tsx
export function KpiCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div
      className="kpi-card"
      data-kpi-card=""
      style={{
        // relative sizing
        padding: '1rem',
        border: '1px solid var(--sl-color-hairline)',
        boxSizing: 'border-box',
        borderRadius: '0.75rem',
        // PRE state: only minimum height; card may not fill grid row completely
        minHeight: 'var(--kpi-card-h)',
        position: 'relative',
        display: 'block',
        overflow: 'hidden',
      }}
    >
      <div
        className="kpi-title"
        style={{ fontSize: '0.75rem', color: '#666', lineHeight: '1.125rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
      >
        {title}
      </div>
      <div
        className="kpi-value"
        data-kpi-value=""
        style={{
          fontSize: 'clamp(1.25rem, 2.2vw, 1.5rem)',
          fontWeight: 700,
          lineHeight: 1.25,
          // PRE state: allow wrapping (may change vertical space)
          position: 'absolute',
          left: '1rem',
          right: '1rem',
          bottom: '1rem',
        }}
      >
        {value}
      </div>
    </div>
  );
}
