// apps/web/src/components/dashboard/types.ts
export type Agg = 'raw' | 'hour' | 'day';

export type MfrrPoint = {
  ts: string;
  total_called_mw: number;
  avg_price_eur_mwh: number | null;
};

export type SurveyRow = {
  respondent_id: string;
  age: number | null;
  gender: string | null;
};

// Lastprofile: dynamische Serien je ausgewählter Gruppe/Spalte
export type LastprofileRow = {
  ts: string;
  // weitere Keys sind die angeforderten Gruppen/Spalten (number | null)
  [key: string]: string | number | null;
};
