import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/stock_models.dart';
import '../services/api_service.dart';

class StockState {
  final List<StockSymbol> symbols;
  final String? activeSymbol;
  final StockSymbol? activeSymbolDetail;
  final String activeTab;
  final String chartType;
  final String baseUrl;
  
  final List<DailyPrice> candles;
  final List<dynamic> heikinAshi;
  final List<dynamic> renkoBricks;
  final List<dynamic> lineBreakLines;
  final List<TechnicalIndicator> indicators;
  final List<CorporateAction> corporateActions;

  final Map<String, dynamic> screenerFilters;
  final List<ScreenerRow> screenerResults;

  final List<SyncJob> syncJobs;
  final Map<String, dynamic> syncStatuses;

  final List<Map<String, dynamic>> aiEvents;
  final String? aiReport;
  final String? aiRecommendation;
  final String? aiConfidence;

  final bool isLoading;
  final bool aiIsLoading;
  final bool isSyncing;
  final String? error;

  StockState({
    this.symbols = const [],
    this.activeSymbol,
    this.activeSymbolDetail,
    this.activeTab = 'explorer',
    this.chartType = 'candles',
    this.baseUrl = 'http://localhost:8000',
    
    this.candles = const [],
    this.heikinAshi = const [],
    this.renkoBricks = const [],
    this.lineBreakLines = const [],
    this.indicators = const [],
    this.corporateActions = const [],

    this.screenerFilters = const {
      'min_rsi': null,
      'max_rsi': null,
      'sma_20_cross': null,
      'sma_50_cross': null,
      'sma_200_cross': null,
      'macd_trend': null,
      'ha_dir': null,
      'renko_dir': null,
      'lb_dir': null,
      'min_weekly_avg_volume': null,
      'volume_breakout': null,
      'limit': 100
    },
    this.screenerResults = const [],

    this.syncJobs = const [],
    this.syncStatuses = const {},

    this.aiEvents = const [],
    this.aiReport,
    this.aiRecommendation,
    this.aiConfidence,

    this.isLoading = false,
    this.aiIsLoading = false,
    this.isSyncing = false,
    this.error,
  });

  StockState copyWith({
    List<StockSymbol>? symbols,
    String? activeSymbol,
    StockSymbol? activeSymbolDetail,
    String? activeTab,
    String? chartType,
    String? baseUrl,
    
    List<DailyPrice>? candles,
    List<dynamic>? heikinAshi,
    List<dynamic>? renkoBricks,
    List<dynamic>? lineBreakLines,
    List<TechnicalIndicator>? indicators,
    List<CorporateAction>? corporateActions,

    Map<String, dynamic>? screenerFilters,
    List<ScreenerRow>? screenerResults,

    List<SyncJob>? syncJobs,
    Map<String, dynamic>? syncStatuses,

    List<Map<String, dynamic>>? aiEvents,
    String? aiReport,
    String? aiRecommendation,
    String? aiConfidence,

    bool? isLoading,
    bool? aiIsLoading,
    bool? isSyncing,
    String? error,
  }) {
    return StockState(
      symbols: symbols ?? this.symbols,
      activeSymbol: activeSymbol ?? this.activeSymbol,
      activeSymbolDetail: activeSymbolDetail ?? this.activeSymbolDetail,
      activeTab: activeTab ?? this.activeTab,
      chartType: chartType ?? this.chartType,
      baseUrl: baseUrl ?? this.baseUrl,
      
      candles: candles ?? this.candles,
      heikinAshi: heikinAshi ?? this.heikinAshi,
      renkoBricks: renkoBricks ?? this.renkoBricks,
      lineBreakLines: lineBreakLines ?? this.lineBreakLines,
      indicators: indicators ?? this.indicators,
      corporateActions: corporateActions ?? this.corporateActions,

      screenerFilters: screenerFilters ?? this.screenerFilters,
      screenerResults: screenerResults ?? this.screenerResults,

      syncJobs: syncJobs ?? this.syncJobs,
      syncStatuses: syncStatuses ?? this.syncStatuses,

      aiEvents: aiEvents ?? this.aiEvents,
      aiReport: aiReport ?? this.aiReport,
      aiRecommendation: aiRecommendation ?? this.aiRecommendation,
      aiConfidence: aiConfidence ?? this.aiConfidence,

      isLoading: isLoading ?? this.isLoading,
      aiIsLoading: aiIsLoading ?? this.aiIsLoading,
      isSyncing: isSyncing ?? this.isSyncing,
      error: error,
    );
  }
}

class StockNotifier extends StateNotifier<StockState> {
  final ApiService _apiService;

  StockNotifier(this._apiService) : super(StockState(baseUrl: _apiService.baseUrl));

  void setActiveTab(String tab) {
    state = state.copyWith(activeTab: tab);
  }

  void setChartType(String type) {
    state = state.copyWith(chartType: type);
  }

  void setScreenerFilters(Map<String, dynamic> filters) {
    state = state.copyWith(
      screenerFilters: {...state.screenerFilters, ...filters},
    );
  }

  void resetScreenerFilters() {
    state = state.copyWith(
      screenerFilters: const {
        'min_rsi': null,
        'max_rsi': null,
        'sma_20_cross': null,
        'sma_50_cross': null,
        'sma_200_cross': null,
        'macd_trend': null,
        'ha_dir': null,
        'renko_dir': null,
        'lb_dir': null,
        'min_weekly_avg_volume': null,
        'volume_breakout': null,
        'limit': 100
      },
    );
  }

  void clearAiConsole() {
    state = state.copyWith(
      aiEvents: [],
      aiReport: null,
      aiRecommendation: null,
      aiConfidence: null,
    );
  }

  Future<void> fetchSymbols({bool activeOnly = true}) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final symbols = await _apiService.getAllSymbols(activeOnly: activeOnly);
      state = state.copyWith(symbols: symbols, isLoading: false);
      
      // Auto-select first active ticker if none is active
      if (symbols.isNotEmpty && state.activeSymbol == null) {
        await setSelectedSymbol(symbols[0].symbol);
      }
    } catch (e, stack) {
      print('=== ERROR IN FETCH SYMBOLS ===');
      print(e);
      print(stack);
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> setSelectedSymbol(String symbol) async {
    state = state.copyWith(activeSymbol: symbol, isLoading: true, error: null);
    try {
      final detail = await _apiService.getSymbolDetail(symbol);
      state = state.copyWith(activeSymbolDetail: detail);
      await fetchActiveSymbolData();
    } catch (e, stack) {
      print('=== ERROR IN SET SELECTED SYMBOL ===');
      print(e);
      print(stack);
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> fetchActiveSymbolData() async {
    final symbol = state.activeSymbol;
    if (symbol == null) return;

    state = state.copyWith(isLoading: true, error: null);
    try {
      final results = await Future.wait([
        _apiService.getCandles(symbol),
        _apiService.getHeikinAshi(symbol),
        _apiService.getRenkoBricks(symbol),
        _apiService.getLineBreakLines(symbol),
        _apiService.getIndicators(symbol),
        _apiService.getCorporateActions(symbol),
      ]);

      state = state.copyWith(
        candles: results[0] as List<DailyPrice>,
        heikinAshi: results[1],
        renkoBricks: results[2],
        lineBreakLines: results[3],
        indicators: results[4] as List<TechnicalIndicator>,
        corporateActions: results[5] as List<CorporateAction>,
        isLoading: false,
      );
    } catch (e, stack) {
      print('=== ERROR IN FETCH ACTIVE SYMBOL DATA ===');
      print(e);
      print(stack);
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> runScreener() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final cleanFilters = Map<String, dynamic>.from(state.screenerFilters);
      // Strip out 'ANY' placeholders before posting
      cleanFilters.forEach((key, value) {
        if (value == 'ANY') cleanFilters[key] = null;
      });

      final results = await _apiService.runScreener(cleanFilters);
      state = state.copyWith(screenerResults: results, isLoading: false);
    } catch (e) {
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> fetchSyncLogs() async {
    state = state.copyWith(isSyncing: true, error: null);
    try {
      final jobs = await _apiService.getSyncJobs();
      final statusesList = await _apiService.getSyncStatus();

      int synced = 0;
      int failed = 0;
      int pending = 0;
      for (final s in statusesList) {
        final String status = s['last_attempt_status'] ?? 'PENDING';
        if (status == 'SUCCESS') {
          synced++;
        } else if (status == 'FAILED') {
          failed++;
        } else {
          pending++;
        }
      }

      final String statusStr = jobs.isNotEmpty && jobs[0].status == 'RUNNING' ? 'RUNNING' : 'IDLE';

      final Map<String, dynamic> statusesMap = {
        'status': statusStr,
        'pending_symbols': pending,
        'failed_symbols': failed,
        'synced_symbols': synced,
      };

      state = state.copyWith(
        syncJobs: jobs,
        syncStatuses: statusesMap,
        isSyncing: false,
      );
    } catch (e) {
      state = state.copyWith(error: e.toString(), isSyncing: false);
    }
  }

  Future<void> triggerSync() async {
    state = state.copyWith(isSyncing: true, error: null);
    try {
      await _apiService.triggerFullSync();
      await fetchSyncLogs();
    } catch (e) {
      state = state.copyWith(error: e.toString(), isSyncing: false);
    }
  }

  Future<void> triggerSymbolSync(String symbol) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _apiService.triggerSymbolSync(symbol);
      await fetchActiveSymbolData();
    } catch (e) {
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> triggerRecalculate() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _apiService.triggerRecalculate(symbol: state.activeSymbol);
      await fetchActiveSymbolData();
    } catch (e) {
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> runAiWorkflow(String prompt) async {
    clearAiConsole();
    state = state.copyWith(aiIsLoading: true);
    
    try {
      final stream = _apiService.runAiWorkflowStream(prompt);
      await for (final rawEvent in stream) {
        final Map<String, dynamic> event = jsonDecode(rawEvent);
        final eventType = event['event'];
        final eventData = event['data'];
        
        state = state.copyWith(
          aiEvents: [...state.aiEvents, event],
        );

        if (eventType == 'complete' && eventData != null) {
          state = state.copyWith(
            aiReport: eventData['report'],
            aiRecommendation: eventData['recommendation'],
            aiConfidence: eventData['confidence'],
          );
        }
      }
      state = state.copyWith(aiIsLoading: false);
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        aiIsLoading: false,
        aiEvents: [
          ...state.aiEvents,
          {
            'event': 'error',
            'data': 'Failed to execute AI agent: ${e.toString()}'
          }
        ]
      );
    }
  }

  Future<void> updateBaseUrl(String newUrl) async {
    state = state.copyWith(baseUrl: newUrl, isLoading: true, error: null);
    _apiService.baseUrl = newUrl;
    try {
      await _apiService.checkHealth();
      await fetchSymbols();
    } catch (e) {
      state = state.copyWith(error: 'Failed to connect to backend: ${e.toString()}', isLoading: false);
    }
  }
}

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

final stockProvider = StateNotifierProvider<StockNotifier, StockState>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return StockNotifier(apiService);
});
