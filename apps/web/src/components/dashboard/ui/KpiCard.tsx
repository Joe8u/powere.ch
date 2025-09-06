// apps/web/src/components/dashboard/ui/KpiCard.tsx
export function KpiCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div
      className="kpi-card"
      style={{
        padding: 16,
        border: '1px solid var(--sl-color-hairline)',
        boxSizing: 'border-box',
        borderRadius: 12,
        minHeight: 120,
        height: '100%',
        display: 'grid',
        gridTemplateRows: '18px 1fr auto',
      }}
    >
      <div
        className="kpi-title"
        style={{ fontSize: 12, color: '#666', lineHeight: '18px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
      >
        {title}
      </div>
      <div className="kpi-value" style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.25, alignSelf: 'end' }}>{value}</div>
    </div>
  );
}
