// apps/web/src/components/dashboard/ui/KpiCard.tsx
export function KpiCard({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div style={{ padding: 16, border: '1px solid #eee', borderRadius: 12 }}>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}