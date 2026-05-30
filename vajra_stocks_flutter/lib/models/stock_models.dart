
class StockSymbol {
  final int id;
  final String symbol;
  final String companyName;
  final String series;
  final bool isActive;
  final String? lastAttemptStatus;

  StockSymbol({
    required this.id,
    required this.symbol,
    required this.companyName,
    required this.series,
    required this.isActive,
    this.lastAttemptStatus,
  });

  factory StockSymbol.fromJson(Map<String, dynamic> json) {
    return StockSymbol(
      id: json['id'] ?? 0,
      symbol: json['symbol'] ?? '',
      companyName: json['company_name'] ?? '',
      series: json['series'] ?? '',
      isActive: json['is_active'] ?? true,
      lastAttemptStatus: json['last_attempt_status'],
    );
  }
}

DateTime _parseDate(dynamic val) {
  if (val == null) return DateTime.now();
  if (val is String) {
    return DateTime.tryParse(val) ?? DateTime.now();
  }
  if (val is DateTime) return val;
  return DateTime.now();
}

class DailyPrice {
  final DateTime tradingDate;
  final double open;
  final double high;
  final double low;
  final double close;
  final double adjClose;
  final int volume;

  DailyPrice({
    required this.tradingDate,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.adjClose,
    required this.volume,
  });

  factory DailyPrice.fromJson(Map<String, dynamic> json) {
    return DailyPrice(
      tradingDate: _parseDate(json['trading_date'] ?? json['time']),
      open: json['open'] != null ? (json['open'] as num).toDouble() : 0.0,
      high: json['high'] != null ? (json['high'] as num).toDouble() : 0.0,
      low: json['low'] != null ? (json['low'] as num).toDouble() : 0.0,
      close: json['close'] != null ? (json['close'] as num).toDouble() : 0.0,
      adjClose: json['adj_close'] != null
          ? (json['adj_close'] as num).toDouble()
          : (json['close'] != null ? (json['close'] as num).toDouble() : 0.0),
      volume: json['volume'] ?? 0,
    );
  }
}

class TechnicalIndicator {
  final DateTime tradingDate;
  final double? rsi14;
  final double? atr14;
  final double? sma20;
  final double? sma50;
  final double? sma200;
  final double? ema9;
  final double? ema21;
  final double? macdLine;
  final double? macdSignal;
  final double? macdHistogram;

  TechnicalIndicator({
    required this.tradingDate,
    this.rsi14,
    this.atr14,
    this.sma20,
    this.sma50,
    this.sma200,
    this.ema9,
    this.ema21,
    this.macdLine,
    this.macdSignal,
    this.macdHistogram,
  });

  factory TechnicalIndicator.fromJson(Map<String, dynamic> json) {
    return TechnicalIndicator(
      tradingDate: _parseDate(json['trading_date'] ?? json['time']),
      rsi14: json['rsi_14'] != null ? (json['rsi_14'] as num).toDouble() : null,
      atr14: json['atr_14'] != null ? (json['atr_14'] as num).toDouble() : null,
      sma20: json['sma_20'] != null ? (json['sma_20'] as num).toDouble() : null,
      sma50: json['sma_50'] != null ? (json['sma_50'] as num).toDouble() : null,
      sma200: json['sma_200'] != null ? (json['sma_200'] as num).toDouble() : null,
      ema9: json['ema_9'] != null ? (json['ema_9'] as num).toDouble() : null,
      ema21: json['ema_21'] != null ? (json['ema_21'] as num).toDouble() : null,
      macdLine: json['macd_line'] != null ? (json['macd_line'] as num).toDouble() : null,
      macdSignal: json['macd_signal'] != null ? (json['macd_signal'] as num).toDouble() : null,
      macdHistogram: json['macd_histogram'] != null ? (json['macd_histogram'] as num).toDouble() : null,
    );
  }
}

class CorporateAction {
  final DateTime actionDate;
  final String actionType;
  final double value;

  CorporateAction({
    required this.actionDate,
    required this.actionType,
    required this.value,
  });

  factory CorporateAction.fromJson(Map<String, dynamic> json) {
    return CorporateAction(
      actionDate: _parseDate(json['action_date']),
      actionType: json['action_type'] ?? '',
      value: json['value'] != null ? (json['value'] as num).toDouble() : 0.0,
    );
  }
}

class ScreenerRow {
  final int symbolId;
  final String symbol;
  final String companyName;
  final DateTime lastTradingDate;
  final double closePrice;
  final double? pricePctChange;
  final int volume;
  final double? haClose;
  final String? haDirection;
  final double? rsi14;
  final String? sma20CrossDirection;
  final String? sma50CrossDirection;
  final String? sma200CrossDirection;
  final String? macdTrend;
  final String? renkoDirection;
  final String? lineBreakDirection;
  final int? weeklyAvgVolume;
  final double? volumeBreakoutRatio;

  ScreenerRow({
    required this.symbolId,
    required this.symbol,
    required this.companyName,
    required this.lastTradingDate,
    required this.closePrice,
    this.pricePctChange,
    required this.volume,
    this.haClose,
    this.haDirection,
    this.rsi14,
    this.sma20CrossDirection,
    this.sma50CrossDirection,
    this.sma200CrossDirection,
    this.macdTrend,
    this.renkoDirection,
    this.lineBreakDirection,
    this.weeklyAvgVolume,
    this.volumeBreakoutRatio,
  });

  factory ScreenerRow.fromJson(Map<String, dynamic> json) {
    return ScreenerRow(
      symbolId: json['symbol_id'] ?? 0,
      symbol: json['symbol'] ?? '',
      companyName: json['company_name'] ?? '',
      lastTradingDate: _parseDate(json['last_trading_date']),
      closePrice: json['close_price'] != null ? (json['close_price'] as num).toDouble() : 0.0,
      pricePctChange: json['price_pct_change'] != null ? (json['price_pct_change'] as num).toDouble() : null,
      volume: json['volume'] ?? 0,
      haClose: json['ha_close'] != null ? (json['ha_close'] as num).toDouble() : null,
      haDirection: json['ha_direction'],
      rsi14: json['rsi_14'] != null ? (json['rsi_14'] as num).toDouble() : null,
      sma20CrossDirection: json['sma_20_cross_direction'],
      sma50CrossDirection: json['sma_50_cross_direction'],
      sma200CrossDirection: json['sma_200_cross_direction'],
      macdTrend: json['macd_trend'],
      renkoDirection: json['renko_direction'],
      lineBreakDirection: json['line_break_direction'],
      weeklyAvgVolume: json['weekly_avg_volume'] != null ? (json['weekly_avg_volume'] as num).toInt() : null,
      volumeBreakoutRatio: json['volume_breakout_ratio'] != null ? (json['volume_breakout_ratio'] as num).toDouble() : null,
    );
  }
}

class SyncJob {
  final int id;
  final String runId;
  final DateTime startTime;
  final DateTime? endTime;
  final String status;
  final int totalSymbols;
  final int processedSymbols;
  final int failedSymbols;
  final int recordsInserted;
  final String? errorSummary;

  SyncJob({
    required this.id,
    required this.runId,
    required this.startTime,
    this.endTime,
    required this.status,
    required this.totalSymbols,
    required this.processedSymbols,
    required this.failedSymbols,
    required this.recordsInserted,
    this.errorSummary,
  });

  factory SyncJob.fromJson(Map<String, dynamic> json) {
    return SyncJob(
      id: json['id'] ?? 0,
      runId: json['run_id'] ?? '',
      startTime: DateTime.parse(json['start_time']),
      endTime: json['end_time'] != null ? DateTime.parse(json['end_time']) : null,
      status: json['status'] ?? 'UNKNOWN',
      totalSymbols: json['total_symbols'] ?? 0,
      processedSymbols: json['processed_symbols'] ?? 0,
      failedSymbols: json['failed_symbols'] ?? 0,
      recordsInserted: json['records_inserted'] ?? 0,
      errorSummary: json['error_summary'],
    );
  }
}
