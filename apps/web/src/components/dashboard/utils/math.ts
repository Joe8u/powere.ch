// apps/web/src/components/dashboard/utils/math.ts
export function avg(xs: Array<number | null | undefined>): number | null {
  const vals = xs.filter((x): x is number => typeof x === 'number' && Number.isFinite(x));
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}