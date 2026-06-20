import React from 'react';
import { useStockStore } from '../store/useStockStore';
import { Gift, Scissors, Calendar } from 'lucide-react';

export const CorporateActionsTimeline: React.FC = () => {
  const { corporateActions, activeSymbol } = useStockStore();

  const sortedActions = [...corporateActions].sort((a, b) => b.action_date.localeCompare(a.action_date));

  return (
    <div className="w-full bg-bg-surface/60 rounded-xl border border-slate-800/80 p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <Calendar className="w-5 h-5 text-purple-500" />
        <h3 className="text-md font-bold text-white tracking-wide">Corporate Events</h3>
      </div>

      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-3 min-h-[140px]">
        {sortedActions.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-center text-slate-500 text-sm py-8">
            No corporate actions recorded for {activeSymbol?.replace('.NS', '')}.
          </div>
        ) : (
          sortedActions.map((act) => {
            const isDividend = act.action_type === 'DIVIDEND';
            return (
              <div 
                key={act.id} 
                className="flex items-start gap-3 p-3 rounded-lg border border-slate-850 bg-slate-900/40 hover:bg-slate-900/70 transition"
              >
                <div className={`p-2 rounded-lg ${
                  isDividend 
                    ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/30' 
                    : 'bg-indigo-950/40 text-indigo-400 border border-indigo-900/30'
                }`}>
                  {isDividend ? <Gift className="w-4 h-4" /> : <Scissors className="w-4 h-4" />}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-sm text-white">
                      {isDividend ? 'Cash Dividend' : 'Stock Split'}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">{act.action_date}</span>
                  </div>
                  
                  <p className="text-xs text-slate-400 mt-1">
                    {isDividend 
                      ? `Distributed ₹${act.value} per equity share.`
                      : `Stock split with ratio ${act.value}:1.`}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
