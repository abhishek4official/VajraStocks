import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';
import '../models/stock_models.dart';

class MetricsTable extends ConsumerWidget {
  const MetricsTable({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    if (state.indicators.isEmpty) {
      return const SizedBox(
        height: 260,
        child: Card(
          child: Center(
            child: Text(
              'No technical indicators calculated yet. Trigger a recalculation job inside the Sync Center.',
              style: TextStyle(color: Color(0xFF94A3B8)),
            ),
          ),
        ),
      );
    }

    return _buildDenseTable(state.indicators);
  }

  Widget _buildDenseTable(List<TechnicalIndicator> indicators) {
    // Show latest 15 indicator logs in reverse chronological order
    final recent = indicators.length > 15
        ? indicators.sublist(indicators.length - 15).reversed.toList()
        : indicators.reversed.toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Row(
                  children: [
                    Icon(Icons.layers, color: VajraTheme.primaryPurple, size: 16),
                    SizedBox(width: 8),
                    Text(
                      'EOD Indicator Logs',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
                    ),
                  ],
                ),
                Text(
                  'Showing latest ${recent.length} trading days',
                  style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8), fontFamily: 'monospace'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columnSpacing: 24,
                headingRowHeight: 32,
                dataRowMinHeight: 36,
                dataRowMaxHeight: 36,
                columns: const [
                  DataColumn(label: Text('Date', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('RSI (14)', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('SMA 20', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('SMA 50', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('SMA 200', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('MACD', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('Signal', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                  DataColumn(label: Text('Histogram', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)))),
                ],
                rows: recent.map((TechnicalIndicator ind) {
                  return DataRow(
                    cells: [
                      // Date
                      DataCell(Text(
                        DateFormat('yyyy-MM-dd').format(ind.tradingDate),
                        style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: Color(0xFF94A3B8)),
                      )),
                      // RSI (14)
                      DataCell(_buildRsiCell(ind.rsi14)),
                      // SMA 20
                      DataCell(Text(
                        ind.sma20?.toStringAsFixed(1) ?? '-',
                        style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0), fontFamily: 'monospace'),
                      )),
                      // SMA 50
                      DataCell(Text(
                        ind.sma50?.toStringAsFixed(1) ?? '-',
                        style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0), fontFamily: 'monospace'),
                      )),
                      // SMA 200
                      DataCell(Text(
                        ind.sma200?.toStringAsFixed(1) ?? '-',
                        style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0), fontFamily: 'monospace'),
                      )),
                      // MACD Line
                      DataCell(Text(
                        ind.macdLine?.toStringAsFixed(2) ?? '-',
                        style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0), fontFamily: 'monospace'),
                      )),
                      // Signal
                      DataCell(Text(
                        ind.macdSignal?.toStringAsFixed(2) ?? '-',
                        style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0), fontFamily: 'monospace'),
                      )),
                      // Histogram
                      DataCell(_buildHistogramCell(ind.macdHistogram)),
                    ],
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRsiCell(double? rsi) {
    if (rsi == null) {
      return const Text('-', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontFamily: 'monospace'));
    }

    final bool isOverbought = rsi >= 70;
    final bool isOversold = rsi <= 30;

    if (isOverbought) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: VajraTheme.accentRed.withValues(alpha: 0.1),
          border: Border.all(color: VajraTheme.accentRed.withValues(alpha: 0.3)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          rsi.toStringAsFixed(2),
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: VajraTheme.accentRed,
            fontFamily: 'monospace',
          ),
        ),
      );
    } else if (isOversold) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: VajraTheme.accentGreen.withValues(alpha: 0.1),
          border: Border.all(color: VajraTheme.accentGreen.withValues(alpha: 0.3)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          rsi.toStringAsFixed(2),
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: VajraTheme.accentGreen,
            fontFamily: 'monospace',
          ),
        ),
      );
    } else {
      return Text(
        rsi.toStringAsFixed(2),
        style: const TextStyle(
          fontSize: 11,
          color: Color(0xFFCBD5E1),
          fontFamily: 'monospace',
        ),
      );
    }
  }

  Widget _buildHistogramCell(double? hist) {
    if (hist == null) {
      return const Text('-', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontFamily: 'monospace'));
    }

    final bool isBullish = hist >= 0;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          isBullish ? Icons.trending_up : Icons.trending_down,
          size: 13,
          color: isBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
        ),
        const SizedBox(width: 4),
        Text(
          hist.toStringAsFixed(2),
          style: TextStyle(
            fontSize: 11,
            color: isBullish ? VajraTheme.accentGreen : VajraTheme.accentRed,
            fontFamily: 'monospace',
          ),
        ),
      ],
    );
  }
}

