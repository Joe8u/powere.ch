// Umrechnungen & Formatter (de-CH)
export const chfKwhToEurMwh = (chf_kwh: number, fx_eur_chf = 1) =>
  (chf_kwh / fx_eur_chf) * 1000;

export const eurMwhToChfKwh = (eur_mwh: number, fx_eur_chf = 1) =>
  (eur_mwh * fx_eur_chf) / 1000;

export const nf2 = new Intl.NumberFormat("de-CH", { maximumFractionDigits: 2 });
export const nf3 = new Intl.NumberFormat("de-CH", { maximumFractionDigits: 3 });
export const chf = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  maximumFractionDigits: 3,
});
export const eur = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

export const monthNames = [
  "Jan","Feb","Mrz","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"
];

export const two = (n: number) => (n < 10 ? `0${n}` : `${n}`);
