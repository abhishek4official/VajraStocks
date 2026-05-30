import { create } from 'zustand';
import { apiService } from '../services/api';
import type { 
  SymbolDetail, 
  CandleData, 
  RenkoBrick, 
  LineBreakLine, 
  IndicatorData, 
  ScreenerRow, 
  CorporateAction, 
  SyncJob, 
  SymbolSyncStatus 
} from '../services/api';

interface ScreenerFilters {
  min_rsi?: number;
  max_rsi?: number;
  sma_20_cross?: 'ABOVE' | 'BELOW';
  sma_50_cross?: 'ABOVE' | 'BELOW';
  sma_200_cross?: 'ABOVE' | 'BELOW';
  macd_trend?: 'BULLISH' | 'BEARISH';
  ha_dir?: 'UP' | 'DOWN';
  renko_dir?: 'UP' | 'DOWN';
  lb_dir?: 'UP' | 'DOWN';
  min_weekly_avg_volume?: number;
  volume_breakout?: 'ANY' | '1.5X' | '2.0X' | '3.0X';
  limit?: number;
}

interface StockState {
  // Data States
  symbols: SymbolDetail[];
  activeSymbol: string | null;
  activeSymbolDetail: SymbolDetail | null;
  activeTab: 'explorer' | 'screener' | 'sync' | 'ai-research';
  chartType: 'candles' | 'heikin-ashi' | 'renko' | 'line-break';
  
  // Charts & Technical Data
  candles: CandleData[];
  heikinAshi: CandleData[];
  renkoBricks: RenkoBrick[];
  lineBreakLines: LineBreakLine[];
  indicators: IndicatorData[];
  corporateActions: CorporateAction[];
  
  // Screener States
  screenerFilters: ScreenerFilters;
  screenerResults: ScreenerRow[];
  
  // Sync Statuses
  syncJobs: SyncJob[];
  syncStatuses: SymbolSyncStatus[];
  
  // AI Quant Agent States
  aiQuery: string;
  aiIsLoading: boolean;
  aiEvents: { agent?: string; status: string; data?: any }[];
  aiReport: string | null;
  aiRecommendation: string | null;
  aiConfidence: string | null;
  
  // Loading & Global States
  isLoading: boolean;
  isSyncing: boolean;
  error: string | null;

  // Actions
  setActiveTab: (tab: 'explorer' | 'screener' | 'sync' | 'ai-research') => void;
  setChartType: (type: 'candles' | 'heikin-ashi' | 'renko' | 'line-break') => void;
  setScreenerFilters: (filters: Partial<ScreenerFilters>) => void;
  setAiQuery: (query: string) => void;
  clearAiConsole: () => void;
  
  // Async Thunks / Async operations
  fetchSymbols: (activeOnly?: boolean) => Promise<void>;
  setSelectedSymbol: (symbol: string) => Promise<void>;
  fetchActiveSymbolData: () => Promise<void>;
  runScreener: () => Promise<void>;
  fetchSyncLogs: () => Promise<void>;
  triggerFullSync: () => Promise<void>;
  triggerSymbolSync: (symbol: string) => Promise<void>;
  triggerRecalculate: (symbol?: string) => Promise<void>;
  runAiWorkflow: (prompt: string) => Promise<void>;
}

const getInitialTab = (): 'explorer' | 'screener' | 'sync' | 'ai-research' => {
  const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
  if (['explorer', 'screener', 'sync', 'ai-research'].includes(path)) {
    return path as any;
  }
  return 'explorer';
};

export const useStockStore = create<StockState>((set, get) => ({
  // Initial states
  symbols: [],
  activeSymbol: null,
  activeSymbolDetail: null,
  activeTab: getInitialTab(),
  chartType: 'candles',
  
  candles: [],
  heikinAshi: [],
  renkoBricks: [],
  lineBreakLines: [],
  indicators: [],
  corporateActions: [],
  
  screenerFilters: {
    min_rsi: undefined,
    max_rsi: undefined,
    sma_20_cross: undefined,
    sma_50_cross: undefined,
    sma_200_cross: undefined,
    macd_trend: undefined,
    ha_dir: undefined,
    renko_dir: undefined,
    lb_dir: undefined,
    min_weekly_avg_volume: undefined,
    volume_breakout: undefined,
    limit: 100
  },
  screenerResults: [],
  
  syncJobs: [],
  syncStatuses: [],
  
  // AI Quant Agent initial states
  aiQuery: '',
  aiIsLoading: false,
  aiEvents: [],
  aiReport: null,
  aiRecommendation: null,
  aiConfidence: null,
  
  isLoading: false,
  isSyncing: false,
  error: null,

  // Basic Setters
  setActiveTab: (activeTab) => {
    set({ activeTab });
    const cleanPath = `/${activeTab === 'explorer' ? '' : activeTab}`;
    if (window.location.pathname !== cleanPath) {
      window.history.pushState(null, '', cleanPath);
    }
  },
  setChartType: (chartType) => set({ chartType }),
  setScreenerFilters: (filters) => set({ 
    screenerFilters: { ...get().screenerFilters, ...filters } 
  }),
  setAiQuery: (aiQuery) => set({ aiQuery }),
  clearAiConsole: () => set({ aiEvents: [], aiReport: null, aiRecommendation: null, aiConfidence: null }),

  // Async Operations
  fetchSymbols: async (activeOnly = true) => {
    set({ isLoading: true, error: null });
    try {
      const symbols = await apiService.getAllSymbols(activeOnly);
      set({ symbols, isLoading: false });
      
      // Auto-select first active symbol if none is active
      if (symbols.length > 0 && !get().activeSymbol) {
        await get().setSelectedSymbol(symbols[0].symbol);
      }
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch symbols', isLoading: false });
    }
  },

  setSelectedSymbol: async (symbol) => {
    set({ activeSymbol: symbol, isLoading: true, error: null });
    try {
      const detail = await apiService.getSymbolDetail(symbol);
      set({ activeSymbolDetail: detail });
      await get().fetchActiveSymbolData();
    } catch (err: any) {
      set({ error: err.message || 'Failed to load symbol details', isLoading: false });
    }
  },

  fetchActiveSymbolData: async () => {
    const symbol = get().activeSymbol;
    if (!symbol) return;
    
    set({ isLoading: true, error: null });
    try {
      // Parallel execution for high speed EOD loading
      const [
        candles,
        heikinAshi,
        renkoBricks,
        lineBreakLines,
        indicators,
        corporateActions
      ] = await Promise.all([
        apiService.getCandles(symbol),
        apiService.getHeikinAshi(symbol),
        apiService.getRenkoBricks(symbol),
        apiService.getLineBreakLines(symbol),
        apiService.getIndicators(symbol),
        apiService.getCorporateActions(symbol)
      ]);

      set({ 
        candles,
        heikinAshi,
        renkoBricks,
        lineBreakLines,
        indicators,
        corporateActions,
        isLoading: false 
      });
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch symbol indicators or charts', isLoading: false });
    }
  },

  runScreener: async () => {
    set({ isLoading: true, error: null });
    try {
      const results = await apiService.runScreenerPost(get().screenerFilters);
      set({ screenerResults: results, isLoading: false });
    } catch (err: any) {
      set({ error: err.message || 'Failed to execute screening sweep', isLoading: false });
    }
  },

  fetchSyncLogs: async () => {
    set({ isSyncing: true, error: null });
    try {
      const [syncJobs, syncStatuses] = await Promise.all([
        apiService.getSyncJobs(20),
        apiService.getSyncStatus()
      ]);
      set({ syncJobs, syncStatuses, isSyncing: false });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load sync logs', isSyncing: false });
    }
  },

  triggerFullSync: async () => {
    set({ error: null });
    try {
      await apiService.triggerFullSync();
      // Polling or refresh after brief delay
      setTimeout(() => get().fetchSyncLogs(), 1500);
    } catch (err: any) {
      set({ error: err.message || 'Failed to trigger full EOD sync' });
    }
  },

  triggerSymbolSync: async (symbol) => {
    set({ error: null });
    try {
      await apiService.triggerSymbolSync(symbol);
      setTimeout(() => {
        get().fetchSyncLogs();
        if (get().activeSymbol === symbol) {
          get().fetchActiveSymbolData();
        }
      }, 1500);
    } catch (err: any) {
      set({ error: err.message || `Failed to trigger sync for ${symbol}` });
    }
  },

  triggerRecalculate: async (symbol) => {
    set({ error: null });
    try {
      await apiService.triggerRecalculation(symbol);
      setTimeout(() => {
        get().fetchSyncLogs();
        if (symbol && get().activeSymbol === symbol) {
          get().fetchActiveSymbolData();
        } else if (!symbol) {
          get().fetchActiveSymbolData();
        }
      }, 2000);
    } catch (err: any) {
      set({ error: err.message || 'Failed to trigger calculations' });
    }
  },

  runAiWorkflow: async (prompt: string) => {
    set({ 
      aiIsLoading: true, 
      aiQuery: prompt, 
      aiEvents: [], 
      aiReport: null, 
      aiRecommendation: null, 
      aiConfidence: null 
    });
    
    try {
      const url = `http://localhost:8000/api/v1/agents/chat-stream?prompt=${encodeURIComponent(prompt)}`;
      const eventSource = new EventSource(url);
      
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { event: eventType, data } = payload;
          
          if (eventType === 'started') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { status: data }]
            }));
          } 
          else if (eventType === 'intent_detected') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { 
                status: `Intent Detected: ${data.intent.toUpperCase()}${data.symbol ? ` for ${data.symbol}` : ''}`,
                data: data
              }]
            }));
          } 
          else if (eventType === 'agent_active') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { 
                agent: data.agent, 
                status: data.status,
                data: data
              }]
            }));
          } 
          else if (eventType === 'complete') {
            set({
              aiReport: data.report || null,
              aiRecommendation: data.recommendation || null,
              aiConfidence: data.confidence || null,
              screenerResults: data.screener_results || get().screenerResults,
              aiIsLoading: false
            });
            if (data.screener_results && data.screener_results.length > 0) {
              get().setActiveTab('screener');
            }
            eventSource.close();
          } 
          else if (eventType === 'error') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { status: `Error: ${data}` }],
              aiIsLoading: false
            }));
            eventSource.close();
          }
        } catch (err) {
          console.error('Failed to parse SSE event data', err);
        }
      };
      
      eventSource.onerror = () => {
        set((state) => ({
          aiEvents: [...state.aiEvents, { status: 'Connection error in AI Quant pipeline.' }],
          aiIsLoading: false
        }));
        eventSource.close();
      };
      
    } catch (err: any) {
      set({ 
        aiEvents: [{ status: `Failed to initiate AI stream: ${err.message}` }], 
        aiIsLoading: false 
      });
    }
  }
}));
