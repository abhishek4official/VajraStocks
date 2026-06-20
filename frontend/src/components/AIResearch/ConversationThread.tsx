import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, Plus, Sparkles, Bot } from 'lucide-react';
import { useConversationStore, AGENT_TYPES } from '../../store/useConversationStore';
import { MessageBubble } from './MessageBubble';

const SAMPLE_QUERIES: Record<string, string[]> = {
  analyze_stock:    ['Analyze TCS.NS for swing trade', 'Analyze RELIANCE.NS setup', 'Score INFY.NS technicals'],
  breakout_scan:    ["Find today's breakout opportunities", 'Scan for momentum stocks', 'Which stocks are breaking out?'],
  swing_trade_scan: ['Find swing trade setups', 'Top reversal candidates today', 'Best swing entries this week'],
  market_regime:    ['What is the current Nifty trend?', 'Market regime analysis', 'Is Nifty bullish or bearish?'],
};

function StreamingIndicator() {
  const { streamEvents } = useConversationStore();
  const last = [...streamEvents].reverse().find((e) => e.type === 'agent_active' || e.type === 'intent_detected');

  if (!last) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Loader2 size={13} className="animate-spin text-purple-400" />
        <span>Starting pipeline…</span>
      </div>
    );
  }

  const data = last.data as Record<string, string>;
  const label = last.type === 'intent_detected'
    ? `Detected intent: ${data?.intent?.replace(/_/g, ' ')}`
    : data?.status ?? 'Processing…';

  return (
    <div className="flex items-center gap-2 text-xs text-slate-400">
      <Loader2 size={13} className="animate-spin text-purple-400 shrink-0" />
      <span>{label}</span>
    </div>
  );
}

export function ConversationThread() {
  const { messages, isStreaming, activeAgent, sendMessage, startNewThread } = useConversationStore();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isStreaming]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = input.trim();
    if (!prompt || isStreaming) return;
    setInput('');
    await sendMessage(prompt);
  };

  const agentMeta = AGENT_TYPES.find((a) => a.id === activeAgent);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex flex-col bg-[#07080a]">
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-10 text-center">
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4 border border-slate-800"
            style={{ backgroundColor: `${agentMeta?.color}18` }}
          >
            <Sparkles size={22} style={{ color: agentMeta?.color }} />
          </div>
          <h2 className="text-base font-semibold text-slate-200 mb-1">{agentMeta?.label}</h2>
          <p className="text-sm text-slate-500 max-w-xs mb-6">{agentMeta?.desc}</p>

          <div className="grid grid-cols-1 gap-2 w-full max-w-sm">
            {(SAMPLE_QUERIES[activeAgent] ?? []).map((q) => (
              <button
                key={q}
                onClick={async () => {
                  setInput(q);
                  if (!isStreaming) {
                    await sendMessage(q);
                  }
                }}
                className="text-left text-xs px-3 py-2.5 rounded-xl border border-slate-800 hover:border-slate-600 hover:bg-slate-800/60 transition-colors text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <InputBar
          input={input}
          setInput={setInput}
          onSubmit={handleSubmit}
          isStreaming={isStreaming}
          agentColor={agentMeta?.color}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-[#07080a]">
      {/* Thread header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-[#0d0f14]">
        <span className="text-xs font-semibold text-slate-400">
          {agentMeta?.label} · {messages.length} message{messages.length !== 1 ? 's' : ''}
        </span>
        <button
          onClick={() => startNewThread(activeAgent)}
          className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-purple-400 transition-colors"
        >
          <Plus size={12} /> New chat
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isStreaming && (
          <div className="flex gap-2 mb-4">
            <div className="shrink-0 w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center mt-1 shrink-0">
              <Bot size={12} className="text-purple-400 animate-pulse" />
            </div>
            <div className="bg-[#121620] border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3">
              <StreamingIndicator />
            </div>
          </div>
        )}
      </div>

      <InputBar
        input={input}
        setInput={setInput}
        onSubmit={handleSubmit}
        isStreaming={isStreaming}
        agentColor={agentMeta?.color}
      />
    </div>
  );
}

function InputBar({
  input,
  setInput,
  onSubmit,
  isStreaming,
  agentColor,
}: {
  input: string;
  setInput: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isStreaming: boolean;
  agentColor?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }, [input]);

  return (
    <form
      onSubmit={onSubmit}
      className="shrink-0 border-t border-slate-800 bg-[#0d0f14] px-4 py-3 flex gap-2 items-end"
    >
      <textarea
        ref={textareaRef}
        rows={1}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSubmit(e as unknown as React.FormEvent);
          }
        }}
        placeholder="Ask the agent… (Enter to send, Shift+Enter for new line)"
        disabled={isStreaming}
        className="flex-1 resize-none text-sm border border-slate-700 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-600/50 bg-[#121620] text-slate-200 placeholder-slate-600 disabled:opacity-50"
        style={{ maxHeight: 120, overflowY: 'auto' }}
      />
      <button
        type="submit"
        disabled={isStreaming || !input.trim()}
        className="shrink-0 flex items-center justify-center w-9 h-9 rounded-xl text-white disabled:opacity-40 transition-opacity cursor-pointer"
        style={{ backgroundColor: agentColor ?? '#7c3aed' }}
      >
        {isStreaming ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
      </button>
    </form>
  );
}
