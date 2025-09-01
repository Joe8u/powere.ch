// apps/web/src/components/dashboard/types.ts
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