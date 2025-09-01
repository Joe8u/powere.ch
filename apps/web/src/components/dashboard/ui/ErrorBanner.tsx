// apps/web/src/components/dashboard/ui/ErrorBanner.tsx
export function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 12, borderRadius: 8, background: '#ffe9e9', color: '#8a1f1f', border: '1px solid #f3b4b4' }}>
      {children}
    </div>
  );
}