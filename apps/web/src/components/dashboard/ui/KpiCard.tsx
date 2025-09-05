// apps/web/src/components/dashboard/ui/KpiCard.tsx
export function KpiCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div style={{ padding: 16, border: '1px solid var(--sl-color-hairline)', boxSizing: 'border-box', borderRadius: 12, minHeight: 110, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
