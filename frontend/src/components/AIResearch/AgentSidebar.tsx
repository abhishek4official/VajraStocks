import React, { useEffect } from 'react';
import { MessageSquare, Plus, TrendingUp, Search, BarChart2, Activity } from 'lucide-react';
import { useConversationStore, AGENT_TYPES, type Thread } from '../../store/useConversationStore';

const AGENT_ICONS: Record<string, React.ReactNode> = {
  analyze_stock:    <TrendingUp size={14} />,
  breakout_scan:    <BarChart2 size={14} />,
  swing_trade_scan: <Activity size={14} />,
  market_regime:    <Search size={14} />,
};

function ThreadItem({
  thread,
  isActive,
  onClick,
  activeColor,
}: {
  thread: Thread;
  isActive: boolean;
  onClick: () => void;
  activeColor: string;
}) {
  const date = new Date(thread.last_active_at);
  const label = date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-lg text-xs mb-1 transition-all duration-150 ${
        isActive
          ? 'text-white font-semibold'
          : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 cursor-pointer'
      }`}
      style={isActive ? { backgroundColor: activeColor } : undefined}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="truncate font-medium">{thread.title}</span>
        <span className={`shrink-0 text-[10px] ${isActive ? 'text-white/80' : 'text-slate-600'}`}>{label}</span>
      </div>
      <div className={`text-[10px] mt-0.5 ${isActive ? 'text-white/70' : 'text-slate-600'}`}>
        {thread.message_count} message{thread.message_count !== 1 ? 's' : ''}
      </div>
    </button>
  );
}

export function AgentSidebar() {
  const { threads, activeThreadId, activeAgent, setActiveAgent, selectThread, startNewThread, loadThreads } =
    useConversationStore();

  useEffect(() => {
    loadThreads();
  }, []);

  const handleAgentClick = (agentId: string) => {
    setActiveAgent(agentId);
    loadThreads(agentId);
  };

  const agentThreads = threads.filter((t) => t.agent_type === activeAgent && !t.is_archived);
  const currentAgentMeta = AGENT_TYPES.find((a) => a.id === activeAgent);
  const activeColor = currentAgentMeta?.color ?? '#4f46e5';

  return (
    <aside className="w-52 shrink-0 flex flex-col border-r border-slate-800 bg-[#0d0f14] h-full">
      {/* Agent list */}
      <div className="p-3 border-b border-slate-800">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Agents</p>
        {AGENT_TYPES.map((agent) => (
          <button
            key={agent.id}
            onClick={() => handleAgentClick(agent.id)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-medium mb-1 transition-colors cursor-pointer ${
              activeAgent === agent.id
                ? 'text-white'
                : 'bg-[#121620] border border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-200'
            }`}
            style={activeAgent === agent.id ? { backgroundColor: agent.color } : undefined}
          >
            <span style={{ color: activeAgent === agent.id ? '#fff' : agent.color }}>
              {AGENT_ICONS[agent.id]}
            </span>
            {agent.label}
          </button>
        ))}
      </div>

      {/* Thread history */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">History</p>
          <button
            onClick={() => startNewThread(activeAgent)}
            title="New conversation"
            className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <Plus size={13} />
          </button>
        </div>

        {agentThreads.length === 0 ? (
          <p className="text-[10px] text-slate-600 text-center py-4">No conversations yet</p>
        ) : (
          agentThreads.map((t) => (
            <ThreadItem
              key={t.id}
              thread={t}
              isActive={t.id === activeThreadId}
              onClick={() => selectThread(t.id)}
              activeColor={activeColor}
            />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-slate-800">
        <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
          <MessageSquare size={11} />
          Conversations remembered across sessions
        </div>
      </div>
    </aside>
  );
}
