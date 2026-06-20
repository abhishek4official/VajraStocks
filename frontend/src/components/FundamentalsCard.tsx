import React, { useEffect, useState } from 'react';
import { BarChart2, RefreshCw } from 'lucide-react';
import { apiService } from '../services/api';
import type { SymbolFundamentals } from '../services/api';

interface Props {
  symbol: string;
}

const fmtCr = (v: number | null) => {
  if (v == null) return '—';
  const cr = v / 1e7;
  if (cr >= 1e5) return `₹${(cr / 1e5).toFixed(2)}L Cr`;
  if (cr >= 1e3) return `₹${(cr / 1e3).toFixed(2)}K Cr`;
  return `₹${cr.toFixed(0)} Cr`;
};
const fmtPct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
const fmtNum = (v: number | null, dec = 2) => (v == null ? '—' : v.toFixed(dec));

const Stat: React.FC<{ label: string; value: string; highlight?: 'green' | 'red' | null }> = ({ label, value, highlight }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[10px] text-text-muted uppercase tracking-wide font-semibold">{label}</span>
    <span className={`text-sm font-bold font-mono ${
      highlight === 'green' ? 'text-emerald-400'
      : highlight === 'red' ? 'text-rose-400'
      : 'text-text-main'
    }`}>{value}</span>
  </div>
);

export const FundamentalsCard: React.FC<Props> = ({ symbol }) => {
  const [data, setData] = useState<SymbolFundamentals | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const clean = symbol.replace('.NS', '');

  useEffect(() => {
    setData(null);
    setLoading(true);
    apiService.getFundamentals(clean).then(d => { setData(d); setLoading(false); });
  }, [clean]);

  const handleRefresh = async () => {
    setRefreshing(true);
    const d = await apiService.refreshFundamentals(clean);
    if (d) setData(d);
    setRefreshing(false);
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-text-main tracking-wide">Fundamentals</h3>
          {data?.sector && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-bg-surface border border-border-subtle text-text-muted font-mono">
              {data.sector}
            </span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          title="Refresh from yfinance"
          className="p-1.5 rounded-lg text-text-muted hover:text-text-main hover:bg-bg-surface transition cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-4 text-center animate-pulse">Loading fundamentals…</div>
      ) : data == null ? (
        <div className="text-xs text-text-muted py-4 text-center">
          No data yet.{' '}
          <button onClick={handleRefresh} className="text-blue-400 hover:underline cursor-pointer">Fetch now</button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-x-6 gap-y-3">
          {/* Valuation */}
          <Stat label="Market Cap" value={fmtCr(data.market_cap)} />
          <Stat label="P/E (TTM)" value={fmtNum(data.pe_ratio)} highlight={data.pe_ratio != null ? (data.pe_ratio < 20 ? 'green' : data.pe_ratio > 50 ? 'red' : null) : null} />
          <Stat label="Fwd P/E" value={fmtNum(data.forward_pe)} />
          <Stat label="P/B" value={fmtNum(data.pb_ratio)} highlight={data.pb_ratio != null ? (data.pb_ratio < 3 ? 'green' : data.pb_ratio > 10 ? 'red' : null) : null} />
          <Stat label="EV/EBITDA" value={fmtNum(data.ev_ebitda)} />
          <Stat label="P/S" value={fmtNum(data.price_to_sales)} />

          {/* Income */}
          <Stat label="Revenue" value={fmtCr(data.revenue_ttm)} />
          <Stat label="Net Profit" value={fmtCr(data.net_profit_ttm)} highlight={data.net_profit_ttm != null ? (data.net_profit_ttm > 0 ? 'green' : 'red') : null} />
          <Stat label="EBITDA" value={fmtCr(data.ebitda)} />
          <Stat label="Profit Margin" value={fmtPct(data.profit_margin)} highlight={data.profit_margin != null ? (data.profit_margin > 0.15 ? 'green' : data.profit_margin < 0 ? 'red' : null) : null} />
          <Stat label="Op Margin" value={fmtPct(data.operating_margin)} />
          <Stat label="Gross Margin" value={fmtPct(data.gross_margin)} />

          {/* Quality */}
          <Stat label="ROE" value={fmtPct(data.roe)} highlight={data.roe != null ? (data.roe > 0.15 ? 'green' : data.roe < 0 ? 'red' : null) : null} />
          <Stat label="ROA" value={fmtPct(data.roa)} />
          <Stat label="Debt/Equity" value={fmtNum(data.debt_to_equity)} highlight={data.debt_to_equity != null ? (data.debt_to_equity < 0.5 ? 'green' : data.debt_to_equity > 2 ? 'red' : null) : null} />
          <Stat label="Current Ratio" value={fmtNum(data.current_ratio)} highlight={data.current_ratio != null ? (data.current_ratio > 1.5 ? 'green' : data.current_ratio < 1 ? 'red' : null) : null} />
          <Stat label="EPS (TTM)" value={data.eps_ttm != null ? `₹${fmtNum(data.eps_ttm)}` : '—'} />
          <Stat label="Div Yield" value={fmtPct(data.dividend_yield)} highlight={data.dividend_yield != null && data.dividend_yield > 0.02 ? 'green' : null} />
        </div>
      )}

      {data?.fetched_at && (
        <div className="mt-3 text-[9px] text-text-muted/60 text-right font-mono">
          Source: yfinance · Updated {new Date(data.fetched_at).toLocaleDateString('en-IN')}
        </div>
      )}
    </div>
  );
};
