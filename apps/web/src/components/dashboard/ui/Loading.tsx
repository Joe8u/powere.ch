// apps/web/src/components/dashboard/ui/Loading.tsx
export function Loading({ children = 'Lade…' }: { children?: React.ReactNode }) {
  return <div style={{ opacity: 0.8 }}>{children}</div>;
}