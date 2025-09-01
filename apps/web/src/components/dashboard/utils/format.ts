// apps/web/src/components/dashboard/utils/format.ts

/** ISO-String → "YYYY-MM-DD HH:MM" (lokal, robust) */
export function formatTs(iso: string): string {
  if (!iso) return '–';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;

  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');

  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

/** Zahl hübsch formatieren (de-CH), leeres Dash bei null/NaN */
export function formatNumber(
  n: number | null | undefined,
  fractionDigits = 1
): string {
  if (n == null || !Number.isFinite(n)) return '–';
  return n.toLocaleString('de-CH', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}