import { useMemo } from 'react';
import { Brain, TrendingUp, Flag, Loader2 } from 'lucide-react';
import { useConversationStore } from '../../store/useConversationStore';

const REC_DOT: Record<string, string> = {
  BULLISH: 'bg-emerald-500',
  BEARISH: 'bg-rose-500',
  NEUTRAL: 'bg-slate-500',
  AVOID:   'bg-orange-500',
};

export function ContextPanel() {
  const { messages, streamEvents, isStreaming } = useConversationStore();

  const tickers = useMemo(() => {
    const map = new Map<string, { rec: string | null }>();
    messages
      .filter((m) => m.role === 'agent' && m.recommendation)
      .forEach((m) => {
        const idx = messages.indexOf(m);
        const userMsg = messages.slice(0, idx).reverse().find((x) => x.role === 'user');
        const symbolMatch = userMsg?.content.match(/\b([A-Z]{2,}(?:\.NS)?)\b/);
        if (symbolMatch) {
          map.set(symbolMatch[1].replace('.NS', ''), { rec: m.recommendation });
        }
      });
    return Array.from(map.entries()).slice(-6).reverse();
  }, [messages]);

  const activeNode = useMemo(() => {
    const last = [...streamEvents].reverse().find((e) => e.type === 'agent_active');
    if (!last) return null;
    return (last.data as Record<string, string>)?.status ?? null;
  }, [streamEvents]);

  return (
    <aside className="w-44 shrink-0 border-l border-slate-800 bg-[#0d0f14] p-3 overflow-y-auto">
      {isStreaming && (
        <div className="mb-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Pipeline</p>
          <div className="flex items-start gap-1.5">
            <Loader2 size={11} className="text-purple-400 animate-spin mt-0.5 shrink-0" />
            <span className="text-[10px] text-slate-500 leading-tight">{activeNode ?? 'Starting…'}</span>
          </div>
        </div>
      )}

      {tickers.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1">
            <TrendingUp size={10} /> Active Memory
          </p>
          {tickers.map(([symbol, { rec }]) => (
            <div
              key={symbol}
              className="flex items-center gap-1.5 mb-1.5 bg-[#121620] border border-slate-800 rounded px-2 py-1"
            >
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${REC_DOT[rec ?? 'NEUTRAL'] ?? 'bg-slate-500'}`} />
              <span className="text-[11px] font-semibold text-slate-300">{symbol}</span>
              {rec && <span className="text-[9px] text-slate-500 ml-auto">{rec}</span>}
            </div>
          ))}
        </div>
      )}

      {streamEvents.length > 0 && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1">
            <Brain size={10} /> Steps
          </p>
          {streamEvents.slice(-8).map((e, i) => {
            const data = e.data as Record<string, string>;
            const label =
              e.type === 'intent_detected'
                ? `Intent: ${data?.intent ?? ''}`
                : e.type === 'agent_active'
                ? (data?.agent ?? e.type)
                : e.type;
            return (
              <div key={i} className="flex items-start gap-1.5 mb-1">
                <Flag size={9} className="text-slate-600 mt-0.5 shrink-0" />
                <span className="text-[10px] text-slate-500 leading-tight capitalize">{label}</span>
              </div>
            );
          })}
        </div>
      )}

      {!isStreaming && tickers.length === 0 && streamEvents.length === 0 && (
        <p className="text-[10px] text-slate-600 text-center pt-8 leading-relaxed">
          Agent memory & pipeline steps appear here during a conversation.
        </p>
      )}
    </aside>
  );
}
