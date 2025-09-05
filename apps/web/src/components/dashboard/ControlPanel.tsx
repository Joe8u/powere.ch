import React from 'react';
import type { Agg } from './types';

type Props = {
  agg: Agg;
  onAggChange: (agg: Agg) => void;
  fromVal: string;
  toVal: string;
  onFromChange: (v: string) => void;
  onToChange: (v: string) => void;
  days: number;
  onDaysChange: (n: number) => void;
  onQuickSet: () => void;
  showMw: boolean;
  onShowMw: (b: boolean) => void;
  showPrice: boolean;
  onShowPrice: (b: boolean) => void;
  lpGroups: string[];
  lpSel: string[];
  onToggleGroup: (g: string, checked: boolean) => void;
  showHeader?: boolean; // optional: show the "Control Panel" heading
};

export default function ControlPanel(props: Props) {
  const {
    agg, onAggChange,
    fromVal, toVal, onFromChange, onToChange,
    days, onDaysChange, onQuickSet,
    showMw, onShowMw, showPrice, onShowPrice,
    lpGroups, lpSel, onToggleGroup,
  } = props;
  const { showHeader = true } = props;

  return (
    <section style={{ display: 'grid', gap: 10, alignSelf: 'start', position: 'sticky', top: 0, padding: 8, border: '1px solid #eee', borderRadius: 10 }}>
      {showHeader && <strong>Control Panel</strong>}

      <label>
        Aggregation{' '}
        <select value={agg} onChange={(e) => onAggChange(e.target.value as Agg)}>
          <option value="raw">15-Min</option>
          <option value="hour">Stunde</option>
          <option value="day">Tag</option>
        </select>
      </label>

      <div style={{ display: 'grid', gap: 6 }}>
        <label>
          Von{' '}
          <input type="datetime-local" value={fromVal} onChange={(e) => onFromChange(e.target.value)} />
        </label>
        <label>
          Bis{' '}
          <input type="datetime-local" value={toVal} onChange={(e) => onToChange(e.target.value)} />
        </label>
        <label>
          Schnellauswahl{' '}
          <select value={days} onChange={(e) => onDaysChange(Number(e.target.value))}>
            <option value={1}>letzte 24h</option>
            <option value={3}>letzte 3 Tage</option>
            <option value={7}>letzte 7 Tage</option>
            <option value={30}>letzte 30 Tage</option>
          </select>
        </label>
        <button onClick={onQuickSet} style={{ justifySelf: 'start' }}>Setzen</button>
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        <label>
          mFRR MW anzeigen{' '}
          <input type="checkbox" checked={showMw} onChange={(e) => onShowMw(e.target.checked)} />
        </label>
        <label>
          mFRR Preis anzeigen{' '}
          <input type="checkbox" checked={showPrice} onChange={(e) => onShowPrice(e.target.checked)} />
        </label>
      </div>

      <div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Lastprofile</div>
        <div style={{ display: 'grid', gap: 4 }}>
          {lpGroups.map((g) => (
            <label key={g} style={{ fontSize: 13 }}>
              <input type="checkbox" checked={lpSel.includes(g)} onChange={(e) => onToggleGroup(g, e.target.checked)} />{' '}
              {g}
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}
