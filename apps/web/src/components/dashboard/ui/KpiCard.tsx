// apps/web/src/components/dashboard/ui/KpiCard.tsx
export function KpiCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div
      className="kpi-card"
      data-kpi-card=""
      style={{
        // Variant A: fixed height to match grid row and stable layout via flex
        padding: '1rem',
        margin: 0,
        border: '1px solid var(--sl-color-hairline)',
        boxSizing: 'border-box',
        borderRadius: '0.75rem',
        // Force card height to match grid track height variable for uniform boxes
        height: 'var(--kpi-card-h)',
        alignSelf: 'stretch',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
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
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </div>
    </div>
  );
}
