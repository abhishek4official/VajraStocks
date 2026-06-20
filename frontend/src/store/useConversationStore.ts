import { create } from 'zustand';
import { API_BASE } from '../lib/apiBase';

export interface Thread {
  id: string;
  agent_type: string;
  title: string;
  message_count: number;
  last_active_at: string;
  is_archived: boolean;
}

export interface ConversationMessage {
  id: number;
  thread_id: string;
  role: 'user' | 'agent';
  content: string;
  recommendation: string | null;
  confidence: string | null;
  annotation: string | null;
  is_summarized: boolean;
  created_at: string;
}

export interface StreamEvent {
  type: 'started' | 'intent_detected' | 'agent_active' | 'complete' | 'error';
  data: unknown;
  timestamp: number;
}

interface ConversationState {
  threads: Thread[];
  activeThreadId: string | null;
  activeAgent: string;
  messages: ConversationMessage[];
  streamEvents: StreamEvent[];
  isStreaming: boolean;
  report: string | null;
  recommendation: string | null;
  confidence: string | null;
  screenerResults: unknown[];
  error: string | null;

  loadThreads: (agentType?: string) => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  startNewThread: (agentType: string) => Promise<string>;
  setActiveAgent: (agent: string) => void;
  sendMessage: (prompt: string) => Promise<void>;
  addAnnotation: (messageId: number, annotation: string) => Promise<void>;
  clearStream: () => void;
}

export const AGENT_TYPES = [
  { id: 'analyze_stock',    label: 'Stock Analyzer',    color: '#4f46e5', desc: 'Deep technical analysis & trade plan for a single ticker' },
  { id: 'breakout_scan',    label: 'Breakout Scanner',  color: '#10b981', desc: 'Find volume breakout & momentum opportunities' },
  { id: 'swing_trade_scan', label: 'Swing Scanner',     color: '#f59e0b', desc: 'Discover high-probability swing reversal setups' },
  { id: 'market_regime',    label: 'Market Regime',     color: '#ef4444', desc: 'Classify current Nifty macro trend & volatility state' },
] as const;

export const useConversationStore = create<ConversationState>((set, get) => ({
  threads: [],
  activeThreadId: null,
  activeAgent: 'analyze_stock',
  messages: [],
  streamEvents: [],
  isStreaming: false,
  report: null,
  recommendation: null,
  confidence: null,
  screenerResults: [],
  error: null,

  setActiveAgent: (agent) => set({ activeAgent: agent }),

  loadThreads: async (agentType) => {
    try {
      const params = new URLSearchParams();
      if (agentType) params.set('agent_type', agentType);
      const res = await fetch(`${API_BASE}/conversations/threads?${params}`);
      if (!res.ok) return;
      const threads: Thread[] = await res.json();
      set({ threads });
    } catch {
      // non-critical — sidebar just stays empty
    }
  },

  selectThread: async (threadId) => {
    set({ activeThreadId: threadId, messages: [], report: null, recommendation: null, confidence: null });
    try {
      const res = await fetch(`${API_BASE}/conversations/threads/${threadId}/messages?limit=100`);
      if (!res.ok) return;
      const messages: ConversationMessage[] = await res.json();
      // Last agent message may have report embedded in content
      const lastAgent = [...messages].reverse().find((m) => m.role === 'agent');
      set({
        messages,
        recommendation: lastAgent?.recommendation ?? null,
        confidence: lastAgent?.confidence ?? null,
      });
    } catch {
      // ignore
    }
  },

  startNewThread: async (agentType) => {
    const res = await fetch(`${API_BASE}/conversations/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_type: agentType, title: 'New conversation' }),
    });
    if (!res.ok) throw new Error('Failed to create thread');
    const thread: Thread = await res.json();
    set((state) => ({ threads: [thread, ...state.threads], activeThreadId: thread.id }));
    return thread.id;
  },

  sendMessage: async (prompt) => {
    const { activeThreadId, activeAgent } = get();

    // Ensure we have an active thread
    let threadId = activeThreadId;
    if (!threadId) {
      threadId = await get().startNewThread(activeAgent);
    }

    // Optimistically add the user message to the local list
    const optimisticUser: ConversationMessage = {
      id: Date.now(),
      thread_id: threadId,
      role: 'user',
      content: prompt,
      recommendation: null,
      confidence: null,
      annotation: null,
      is_summarized: false,
      created_at: new Date().toISOString(),
    };
    set((state) => ({
      messages: [...state.messages, optimisticUser],
      streamEvents: [],
      isStreaming: true,
      report: null,
      recommendation: null,
      confidence: null,
      error: null,
    }));

    // Persist user message to DB (fire and forget)
    fetch(`${API_BASE}/conversations/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, role: 'user', content: prompt }),
    }).catch(() => {});

    // Auto-title thread after first message (use first 60 chars of prompt)
    if (get().messages.length <= 1) {
      const title = prompt.slice(0, 60) + (prompt.length > 60 ? '…' : '');
      fetch(`${API_BASE}/conversations/threads/${threadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      }).catch(() => {});
    }

    const url = `${API_BASE}/agents/chat-stream?prompt=${encodeURIComponent(prompt)}&thread_id=${encodeURIComponent(threadId)}`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const eventType: string = payload.event;
        const data = payload.data;

        const streamEvent: StreamEvent = { type: eventType as StreamEvent['type'], data, timestamp: Date.now() };
        set((state) => ({ streamEvents: [...state.streamEvents, streamEvent] }));

        if (eventType === 'complete') {
          const report: string = (data as Record<string, string>).report ?? '';
          const recommendation = (data as Record<string, string>).recommendation ?? null;
          const confValue = (data as Record<string, string>).confidence ?? null;
          const screenerResults = (data as Record<string, unknown[]>).screener_results ?? [];
          const returnedThreadId = (data as Record<string, string>).thread_id ?? threadId;

          // Persist agent response to DB
          fetch(`${API_BASE}/conversations/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              thread_id: returnedThreadId,
              role: 'agent',
              content: report,
              recommendation,
              confidence: confValue,
            }),
          }).catch(() => {});

          const agentMsg: ConversationMessage = {
            id: Date.now() + 1,
            thread_id: returnedThreadId,
            role: 'agent',
            content: report,
            recommendation,
            confidence: confValue,
            annotation: null,
            is_summarized: false,
            created_at: new Date().toISOString(),
          };

          set((state) => ({
            messages: [...state.messages, agentMsg],
            report,
            recommendation,
            confidence: confValue,
            screenerResults,
            isStreaming: false,
            activeThreadId: returnedThreadId,
          }));

          // Refresh thread list so title/count updates
          get().loadThreads();
          es.close();
        } else if (eventType === 'error') {
          const errText = String(data);
          const errMsg: ConversationMessage = {
            id: Date.now() + 1,
            thread_id: threadId!,
            role: 'agent',
            content: `**Error:** ${errText}`,
            recommendation: null,
            confidence: null,
            annotation: null,
            is_summarized: false,
            created_at: new Date().toISOString(),
          };
          set((state) => ({
            messages: [...state.messages, errMsg],
            error: errText,
            isStreaming: false,
          }));
          es.close();
        }
      } catch {
        // ignore malformed SSE
      }
    };

    es.onerror = () => {
      const errMsg: ConversationMessage = {
        id: Date.now() + 1,
        thread_id: threadId!,
        role: 'agent',
        content: '**Error:** Lost connection to the AI pipeline. Please try again.',
        recommendation: null,
        confidence: null,
        annotation: null,
        is_summarized: false,
        created_at: new Date().toISOString(),
      };
      set((state) => ({
        messages: [...state.messages, errMsg],
        error: 'Connection lost',
        isStreaming: false,
      }));
      es.close();
    };
  },

  addAnnotation: async (messageId, annotation) => {
    await fetch(`${API_BASE}/conversations/messages/${messageId}/annotation`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ annotation }),
    });
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, annotation } : m
      ),
    }));
  },

  clearStream: () => set({ streamEvents: [], report: null, recommendation: null, confidence: null, error: null }),
}));
