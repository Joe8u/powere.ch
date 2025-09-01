// apps/web/src/components/dashboard/sections/SurveyList.tsx
import type { SurveyRow } from '../types';

export function SurveyList({ rows }: { rows: SurveyRow[] }) {
  return (
    <section>
      <h3>Survey (Beispiel: 5 Zeilen)</h3>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {rows.map((r) => (
          <li key={r.respondent_id}>
            #{r.respondent_id} – {r.age ?? '–'} Jahre – {r.gender ?? '–'}
          </li>
        ))}
      </ul>
    </section>
  );
}