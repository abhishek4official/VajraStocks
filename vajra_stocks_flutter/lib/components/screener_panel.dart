import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';
import '../models/stock_models.dart';

class ScreenerPanel extends ConsumerStatefulWidget {
  const ScreenerPanel({super.key});

  @override
  ConsumerState<ScreenerPanel> createState() => _ScreenerPanelState();
}

class _StockInspectAction {
  static void inspect(WidgetRef ref, String symbol) {
    final notifier = ref.read(stockProvider.notifier);
    notifier.setSelectedSymbol(symbol);
    notifier.setActiveTab('explorer');
  }
}

class _ScreenerPanelState extends ConsumerState<ScreenerPanel> {
  // Local sorting states
  String? _sortField;
  bool _sortAscending = true;

  @override
  void initState() {
    super.initState();
    // Run an initial sweep when the panel mounts
    Future.microtask(() => ref.read(stockProvider.notifier).runScreener());
  }

  void _handleSort(String field) {
    setState(() {
      if (_sortField == field) {
        _sortAscending = !_sortAscending;
      } else {
        _sortField = field;
        _sortAscending = true;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(stockProvider);
    final notifier = ref.read(stockProvider.notifier);
    final width = MediaQuery.sizeOf(context).width;

    final bool isMobileOrTablet = width < 1024;
    final int crossAxisCount = width < 600
        ? 2
        : (width < 1024 ? 3 : 6);
    final double childAspectRatio = width < 600
        ? 2.8
        : (width < 1024 ? 3.0 : 2.5);

    // Apply sorting locally
    final sortedResults = [...state.screenerResults];
    if (_sortField != null) {
      sortedResults.sort((a, b) {
        dynamic aVal;
        dynamic bVal;

        if (_sortField == 'symbol') {
          aVal = a.symbol;
          bVal = b.symbol;
        } else if (_sortField == 'company_name') {
          aVal = a.companyName;
          bVal = b.companyName;
        } else if (_sortField == 'close_price') {
          aVal = a.closePrice;
          bVal = b.closePrice;
        } else if (_sortField == 'price_pct_change') {
          aVal = a.pricePctChange ?? 0.0;
          bVal = b.pricePctChange ?? 0.0;
        } else if (_sortField == 'weekly_avg_volume') {
          aVal = a.weeklyAvgVolume ?? 0;
          bVal = b.weeklyAvgVolume ?? 0;
        } else if (_sortField == 'volume_breakout_ratio') {
          aVal = a.volumeBreakoutRatio ?? 1.0;
          bVal = b.volumeBreakoutRatio ?? 1.0;
        } else if (_sortField == 'rsi_14') {
          aVal = a.rsi14 ?? 0.0;
          bVal = b.rsi14 ?? 0.0;
        } else if (_sortField == 'sma_20_cross_direction') {
          aVal = a.sma20CrossDirection ?? '';
          bVal = b.sma20CrossDirection ?? '';
        } else if (_sortField == 'sma_50_cross_direction') {
          aVal = a.sma50CrossDirection ?? '';
          bVal = b.sma50CrossDirection ?? '';
        } else if (_sortField == 'sma_200_cross_direction') {
          aVal = a.sma200CrossDirection ?? '';
          bVal = b.sma200CrossDirection ?? '';
        } else if (_sortField == 'macd_trend') {
          aVal = a.macdTrend ?? '';
          bVal = b.macdTrend ?? '';
        } else if (_sortField == 'ha_direction') {
          aVal = a.haDirection ?? '';
          bVal = b.haDirection ?? '';
        } else if (_sortField == 'renko_direction') {
          aVal = a.renkoDirection ?? '';
          bVal = b.renkoDirection ?? '';
        } else if (_sortField == 'line_break_direction') {
          aVal = a.lineBreakDirection ?? '';
          bVal = b.lineBreakDirection ?? '';
        }

        if (aVal == null) return _sortAscending ? 1 : -1;
        if (bVal == null) return _sortAscending ? -1 : 1;

        return _sortAscending ? aVal.compareTo(bVal) : bVal.compareTo(aVal);
      });
    }

    Widget content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(notifier, state),
        const SizedBox(height: 16),
        _buildFiltersCard(state, notifier, crossAxisCount, childAspectRatio),
        const SizedBox(height: 16),
        isMobileOrTablet
            ? _buildResultsCard(state, sortedResults, isMobileOrTablet: true)
            : Expanded(child: _buildResultsCard(state, sortedResults, isMobileOrTablet: false)),
      ],
    );

    if (isMobileOrTablet) {
      content = SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: content,
      );
    } else {
      content = Padding(
        padding: const EdgeInsets.all(16.0),
        child: content,
      );
    }

    return Scaffold(
      body: content,
    );
  }

  Widget _buildHeader(StockNotifier notifier, StockState state) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Stock Screening Suite',
              style: VajraTheme.darkThemeData.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'Execute quantitative sweeps against the EOD databases.',
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
            ),
          ],
        ),
        ElevatedButton.icon(
          onPressed: () => notifier.runScreener(),
          icon: const Icon(Icons.play_arrow, size: 16),
          label: const Text('Run Sweep'),
          style: ElevatedButton.styleFrom(
            backgroundColor: VajraTheme.primaryPurple,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFiltersCard(StockState state, StockNotifier notifier, int crossAxisCount, double childAspectRatio) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Technical Indicator & Crossover Filters',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
                ),
                TextButton.icon(
                  onPressed: () {
                    notifier.resetScreenerFilters();
                    notifier.runScreener();
                  },
                  icon: const Icon(Icons.refresh, size: 13),
                  label: const Text('Reset Filters', style: TextStyle(fontSize: 11)),
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFF94A3B8),
                  ),
                ),
              ],
            ),
            const Divider(color: Color(0xFF1E293B), height: 16),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: crossAxisCount,
              childAspectRatio: childAspectRatio,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              children: [
                _buildNumberInput(
                  'Min RSI (14)',
                  state.screenerFilters['min_rsi'],
                  (val) => notifier.setScreenerFilters({'min_rsi': val}),
                ),
                _buildNumberInput(
                  'Max RSI (14)',
                  state.screenerFilters['max_rsi'],
                  (val) => notifier.setScreenerFilters({'max_rsi': val}),
                ),
                _buildNumberInput(
                  'Min Weekly Vol',
                  state.screenerFilters['min_weekly_avg_volume'],
                  (val) => notifier.setScreenerFilters({'min_weekly_avg_volume': val}),
                ),
                _buildDropdownInput(
                  'Volume Breakout',
                  state.screenerFilters['volume_breakout'] ?? 'ANY',
                  ['ANY', '1.5X', '2.0X', '3.0X'],
                  (val) => notifier.setScreenerFilters({'volume_breakout': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'SMA 20 Crossover',
                  state.screenerFilters['sma_20_cross'] ?? 'ANY',
                  ['ANY', 'ABOVE', 'BELOW'],
                  (val) => notifier.setScreenerFilters({'sma_20_cross': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'SMA 50 Crossover',
                  state.screenerFilters['sma_50_cross'] ?? 'ANY',
                  ['ANY', 'ABOVE', 'BELOW'],
                  (val) => notifier.setScreenerFilters({'sma_50_cross': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'SMA 200 Crossover',
                  state.screenerFilters['sma_200_cross'] ?? 'ANY',
                  ['ANY', 'ABOVE', 'BELOW'],
                  (val) => notifier.setScreenerFilters({'sma_200_cross': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'MACD Trend',
                  state.screenerFilters['macd_trend'] ?? 'ANY',
                  ['ANY', 'BULLISH', 'BEARISH'],
                  (val) => notifier.setScreenerFilters({'macd_trend': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'Heikin Ashi Trend',
                  state.screenerFilters['ha_dir'] ?? 'ANY',
                  ['ANY', 'UP', 'DOWN'],
                  (val) => notifier.setScreenerFilters({'ha_dir': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'Renko Brick Trend',
                  state.screenerFilters['renko_dir'] ?? 'ANY',
                  ['ANY', 'UP', 'DOWN'],
                  (val) => notifier.setScreenerFilters({'renko_dir': val == 'ANY' ? null : val}),
                ),
                _buildDropdownInput(
                  'Line Break Trend',
                  state.screenerFilters['lb_dir'] ?? 'ANY',
                  ['ANY', 'UP', 'DOWN'],
                  (val) => notifier.setScreenerFilters({'lb_dir': val == 'ANY' ? null : val}),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultsCard(StockState state, List<ScreenerRow> sortedResults, {required bool isMobileOrTablet}) {
    Widget cardContent = Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Screened Matches (${sortedResults.length})',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                if (state.isLoading)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: sortedResults.isEmpty
                  ? const Center(
                      child: Text(
                        'No matching stocks found.',
                        style: TextStyle(color: Color(0xFF94A3B8)),
                      ),
                    )
                  : SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SingleChildScrollView(
                        scrollDirection: Axis.vertical,
                        child: DataTable(
                          columnSpacing: 24,
                          headingRowHeight: 40,
                          dataRowMinHeight: 44,
                          dataRowMaxHeight: 44,
                          sortColumnIndex: _sortField == null ? null : 0,
                          sortAscending: _sortAscending,
                          columns: [
                            DataColumn(
                              label: const Text('Ticker'),
                              onSort: (columnIndex, _) => _handleSort('symbol'),
                            ),
                            const DataColumn(label: Text('Company Name')),
                            DataColumn(
                              label: const Text('Close Price'),
                              onSort: (columnIndex, _) => _handleSort('close_price'),
                            ),
                            DataColumn(
                              label: const Text('Change %'),
                              onSort: (columnIndex, _) => _handleSort('price_pct_change'),
                            ),
                            DataColumn(
                              label: const Text('Weekly Avg Vol'),
                              onSort: (columnIndex, _) => _handleSort('weekly_avg_volume'),
                            ),
                            DataColumn(
                              label: const Text('Vol Breakout'),
                              onSort: (columnIndex, _) => _handleSort('volume_breakout_ratio'),
                            ),
                            DataColumn(
                              label: const Text('RSI (14)'),
                              onSort: (columnIndex, _) => _handleSort('rsi_14'),
                            ),
                            DataColumn(
                              label: const Text('SMA 20'),
                              onSort: (columnIndex, _) => _handleSort('sma_20_cross_direction'),
                            ),
                            DataColumn(
                              label: const Text('SMA 50'),
                              onSort: (columnIndex, _) => _handleSort('sma_50_cross_direction'),
                            ),
                            DataColumn(
                              label: const Text('SMA 200'),
                              onSort: (columnIndex, _) => _handleSort('sma_200_cross_direction'),
                            ),
                            DataColumn(
                              label: const Text('MACD Trend'),
                              onSort: (columnIndex, _) => _handleSort('macd_trend'),
                            ),
                            DataColumn(
                              label: const Text('Heikin Ashi'),
                              onSort: (columnIndex, _) => _handleSort('ha_direction'),
                            ),
                            DataColumn(
                              label: const Text('Renko'),
                              onSort: (columnIndex, _) => _handleSort('renko_direction'),
                            ),
                            DataColumn(
                              label: const Text('Line Break'),
                              onSort: (columnIndex, _) => _handleSort('line_break_direction'),
                            ),
                            const DataColumn(label: Text('Actions')),
                          ],
                          rows: sortedResults.map((ScreenerRow row) {
                            final isBullish = (row.pricePctChange ?? 0.0) >= 0;
                            final isHaBullish = row.haDirection == 'UP';
                            final isRenkoBullish = row.renkoDirection == 'UP';
                            final isLbBullish = row.lineBreakDirection == 'UP';

                            return DataRow(
                              cells: [
                                // Ticker
                                DataCell(Text(
                                  row.symbol.replaceFirst('.NS', ''),
                                  style: const TextStyle(fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                                )),

                                // Company Name
                                DataCell(Text(row.companyName)),

                                // Close Price
                                DataCell(Text('₹${row.closePrice.toStringAsFixed(2)}', style: const TextStyle(fontFamily: 'monospace'))),

                                // Change %
                                DataCell(Text(
                                  '${isBullish ? "+" : ""}${row.pricePctChange?.toStringAsFixed(2)}%',
                                  style: TextStyle(
                                    color: isBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
                                    fontFamily: 'monospace',
                                  ),
                                )),

                                // Weekly Avg Vol
                                DataCell(Text(
                                  _formatVolume(row.weeklyAvgVolume),
                                  style: const TextStyle(fontFamily: 'monospace'),
                                )),

                                // Vol Breakout Ratio
                                DataCell(
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: (row.volumeBreakoutRatio ?? 0) >= 3.0
                                          ? VajraTheme.accentRed.withValues(alpha: 0.1)
                                          : ((row.volumeBreakoutRatio ?? 0) >= 2.0
                                              ? VajraTheme.primaryPurple.withValues(alpha: 0.1)
                                              : ((row.volumeBreakoutRatio ?? 0) >= 1.5
                                                  ? Colors.indigo.withValues(alpha: 0.1)
                                                  : Colors.transparent)),
                                      border: Border.all(
                                        color: (row.volumeBreakoutRatio ?? 0) >= 3.0
                                            ? VajraTheme.accentRed.withValues(alpha: 0.3)
                                            : ((row.volumeBreakoutRatio ?? 0) >= 2.0
                                                ? VajraTheme.primaryPurple.withValues(alpha: 0.3)
                                                : ((row.volumeBreakoutRatio ?? 0) >= 1.5
                                                    ? Colors.indigo.withValues(alpha: 0.3)
                                                    : Colors.transparent)),
                                      ),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      row.volumeBreakoutRatio != null
                                          ? '${row.volumeBreakoutRatio!.toStringAsFixed(2)}x'
                                          : '1.00x',
                                      style: TextStyle(
                                        fontFamily: 'monospace',
                                        fontWeight: (row.volumeBreakoutRatio ?? 0) >= 2.0
                                            ? FontWeight.bold
                                            : FontWeight.normal,
                                        color: (row.volumeBreakoutRatio ?? 0) >= 3.0
                                            ? VajraTheme.accentRed
                                            : ((row.volumeBreakoutRatio ?? 0) >= 2.0
                                                ? VajraTheme.primaryPurple
                                                : ((row.volumeBreakoutRatio ?? 0) >= 1.5
                                                    ? Colors.indigoAccent
                                                    : const Color(0xFF94A3B8))),
                                      ),
                                    ),
                                  ),
                                ),

                                // RSI 14
                                DataCell(
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: (row.rsi14 ?? 0) >= 70
                                          ? VajraTheme.accentRed.withValues(alpha: 0.1)
                                          : ((row.rsi14 ?? 0) <= 30 && row.rsi14 != null
                                              ? VajraTheme.accentGreen.withValues(alpha: 0.1)
                                              : Colors.transparent),
                                      border: Border.all(
                                        color: (row.rsi14 ?? 0) >= 70
                                            ? VajraTheme.accentRed.withValues(alpha: 0.3)
                                            : ((row.rsi14 ?? 0) <= 30 && row.rsi14 != null
                                                ? VajraTheme.accentGreen.withValues(alpha: 0.3)
                                                : Colors.transparent),
                                      ),
                                      borderRadius: BorderRadius.circular(4),
                                      ),
                                    child: Text(
                                      row.rsi14?.toStringAsFixed(1) ?? 'N/A',
                                      style: TextStyle(
                                        fontFamily: 'monospace',
                                        fontWeight: (row.rsi14 ?? 0) >= 70 || (row.rsi14 ?? 0) <= 30
                                            ? FontWeight.bold
                                            : FontWeight.normal,
                                        color: (row.rsi14 ?? 0) >= 70
                                            ? VajraTheme.accentRed
                                            : ((row.rsi14 ?? 0) <= 30 && row.rsi14 != null
                                                ? VajraTheme.accentGreen
                                                : Colors.white),
                                      ),
                                    ),
                                  ),
                                ),

                                // SMA 20
                                DataCell(_buildSmaBadge(row.sma20CrossDirection)),

                                // SMA 50
                                DataCell(_buildSmaBadge(row.sma50CrossDirection)),

                                // SMA 200
                                DataCell(_buildSmaBadge(row.sma200CrossDirection)),

                                // MACD Trend
                                DataCell(
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: row.macdTrend == 'BULLISH'
                                          ? VajraTheme.accentGreen.withValues(alpha: 0.1)
                                          : (row.macdTrend == 'BEARISH'
                                              ? VajraTheme.accentRed.withValues(alpha: 0.1)
                                              : Colors.transparent),
                                      border: Border.all(
                                        color: row.macdTrend == 'BULLISH'
                                            ? VajraTheme.accentGreen.withValues(alpha: 0.3)
                                            : (row.macdTrend == 'BEARISH'
                                                ? VajraTheme.accentRed.withValues(alpha: 0.3)
                                                : Colors.transparent),
                                      ),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      row.macdTrend ?? 'UNKNOWN',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: row.macdTrend == 'BULLISH'
                                            ? VajraTheme.accentGreen
                                            : (row.macdTrend == 'BEARISH'
                                                ? VajraTheme.accentRed
                                                : const Color(0xFF94A3B8)),
                                      ),
                                    ),
                                  ),
                                ),

                                // HA Direction
                                DataCell(Text(
                                  row.haDirection ?? 'NONE',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: isHaBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
                                  ),
                                )),

                                // Renko Direction
                                DataCell(Text(
                                  row.renkoDirection ?? 'NONE',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: isRenkoBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
                                  ),
                                )),

                                // Line Break Direction
                                DataCell(Text(
                                  row.lineBreakDirection ?? 'NONE',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: isLbBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
                                  ),
                                )),

                                // Actions
                                DataCell(
                                  TextButton.icon(
                                    onPressed: () => _StockInspectAction.inspect(ref, row.symbol),
                                    icon: const Icon(Icons.remove_red_eye, size: 12),
                                    label: const Text('Inspect'),
                                    style: TextButton.styleFrom(
                                      foregroundColor: VajraTheme.primaryPurple,
                                      padding: const EdgeInsets.symmetric(horizontal: 8),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );

    if (isMobileOrTablet) {
      return SizedBox(
        height: 520,
        child: cardContent,
      );
    } else {
      return cardContent;
    }
  }

  String _formatVolume(int? vol) {
    if (vol == null) return '-';
    if (vol >= 1000000) return '${(vol / 1000000).toStringAsFixed(2)}M';
    if (vol >= 1000) return '${(vol / 1000).toStringAsFixed(1)}K';
    return vol.toString();
  }

  Widget _buildSmaBadge(String? crossDir) {
    final bool isAbove = crossDir == 'ABOVE';
    final bool isBelow = crossDir == 'BELOW';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: isAbove
            ? Colors.indigo.withValues(alpha: 0.1)
            : (isBelow ? Colors.amber.withValues(alpha: 0.1) : Colors.transparent),
        border: Border.all(
          color: isAbove
              ? Colors.indigo.withValues(alpha: 0.3)
              : (isBelow ? Colors.amber.withValues(alpha: 0.3) : Colors.transparent),
        ),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        crossDir ?? 'UNKNOWN',
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: isAbove
              ? Colors.indigoAccent
              : (isBelow ? Colors.amberAccent : const Color(0xFF94A3B8)),
        ),
      ),
    );
  }

  Widget _buildNumberInput(String label, dynamic value, Function(double?) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
        const SizedBox(height: 6),
        SizedBox(
          height: 36,
          child: TextFormField(
            key: ValueKey(value),
            initialValue: value != null ? value.toString() : '',
            keyboardType: TextInputType.number,
            style: const TextStyle(fontSize: 13),
            onChanged: (val) => onChanged(double.tryParse(val)),
            decoration: InputDecoration(
              contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              fillColor: const Color(0xFF07080A),
              filled: true,
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: const BorderSide(color: Color(0xFF1E293B)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: const BorderSide(color: Color(0xFF7C3AED)),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDropdownInput(String label, String value, List<String> options, Function(String) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
        const SizedBox(height: 6),
        Container(
          height: 36,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: const Color(0xFF07080A),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: const Color(0xFF1E293B)),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: value,
              isExpanded: true,
              style: const TextStyle(fontSize: 13, color: Colors.white),
              dropdownColor: const Color(0xFF0D0F14),
              onChanged: (val) => onChanged(val ?? 'ANY'),
              items: options.map((opt) {
                return DropdownMenuItem(value: opt, child: Text(opt));
              }).toList(),
            ),
          ),
        ),
      ],
    );
  }
}
