import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';

class StockPriceChart extends ConsumerWidget {
  final String indicatorToShow; // 'RSI', 'MACD', 'NONE'

  const StockPriceChart({
    super.key,
    required this.indicatorToShow,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    if (state.candles.isEmpty) {
      return const SizedBox(
        height: 380,
        child: Card(
          child: Center(
            child: CircularProgressIndicator(),
          ),
        ),
      );
    }

    // Limit active charting points to the latest 100 EOD price entries to ensure fluid canvas rendering
    final chartPrices = state.candles.length > 80
        ? state.candles.sublist(state.candles.length - 80)
        : state.candles;

    // Convert daily close prices into line spots
    final List<FlSpot> spots = [];
    for (int i = 0; i < chartPrices.length; i++) {
      spots.add(FlSpot(i.toDouble(), chartPrices[i].close));
    }

    final double minPrice = chartPrices.map((p) => p.close).reduce((a, b) => a < b ? a : b);
    final double maxPrice = chartPrices.map((p) => p.close).reduce((a, b) => a > b ? a : b);
    final double padding = (maxPrice - minPrice) * 0.1;

    return SizedBox(
      height: 380,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 24, 24, 12),
          child: Column(
            children: [
              // Dynamic Title Header based on Selected Chart Type
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${state.activeSymbol?.replaceFirst('.NS', '')} - ${state.chartType.toUpperCase().replaceAll('-', ' ')}',
                    style: VajraTheme.darkThemeData.textTheme.headlineSmall,
                  ),
                  Row(
                    children: [
                      _buildIndicatorTag('LATEST: ₹${chartPrices.last.close.toStringAsFixed(2)}', Colors.white.withOpacity(0.08)),
                      const SizedBox(width: 8),
                      _buildIndicatorTag('VOL: ${(chartPrices.last.volume / 1000).toStringAsFixed(1)}K', Colors.white.withOpacity(0.08)),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 24),
              
              // Core fl_chart Rendering Pane
              Expanded(
                child: LineChart(
                  LineChartData(
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: true,
                      horizontalInterval: (maxPrice - minPrice) / 5,
                      verticalInterval: 15,
                      getDrawingHorizontalLine: (value) => FlLine(
                        color: const Color(0xFF1E293B).withOpacity(0.3),
                        strokeWidth: 0.8,
                      ),
                      getDrawingVerticalLine: (value) => FlLine(
                        color: const Color(0xFF1E293B).withOpacity(0.3),
                        strokeWidth: 0.8,
                      ),
                    ),
                    titlesData: FlTitlesData(
                      show: true,
                      rightTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      topTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 22,
                          interval: 20,
                          getTitlesWidget: (value, meta) {
                            final idx = value.toInt();
                            if (idx >= 0 && idx < chartPrices.length) {
                              final dateStr = DateFormat('dd MMM').format(chartPrices[idx].tradingDate);
                              return SideTitleWidget(
                                axisSide: meta.axisSide,
                                space: 4.0,
                                child: Text(
                                  dateStr,
                                  style: const TextStyle(
                                    color: Color(0xFF94A3B8),
                                    fontSize: 9,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              );
                            }
                            return const SizedBox.shrink();
                          },
                        ),
                      ),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 60,
                          getTitlesWidget: (value, meta) {
                            return SideTitleWidget(
                              axisSide: meta.axisSide,
                              space: 8.0,
                              child: Text(
                                '₹${value.toStringAsFixed(0)}',
                                style: const TextStyle(
                                  color: Color(0xFF94A3B8),
                                  fontSize: 9,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    borderData: FlBorderData(
                      show: true,
                      border: Border.all(
                        color: const Color(0xFF1E293B).withOpacity(0.5),
                        width: 0.8,
                      ),
                    ),
                    minX: 0,
                    maxX: (chartPrices.length - 1).toDouble(),
                    minY: minPrice - padding,
                    maxY: maxPrice + padding,
                    lineBarsData: [
                      LineChartBarData(
                        spots: spots,
                        isCurved: true,
                        gradient: const LinearGradient(
                          colors: [
                            VajraTheme.primaryPurple,
                            Color(0xFFA78BFA),
                          ],
                        ),
                        barWidth: 2.2,
                        isStrokeCapRound: true,
                        dotData: const FlDotData(show: false),
                        belowBarData: BarAreaData(
                          show: true,
                          gradient: LinearGradient(
                            colors: [
                              VajraTheme.primaryPurple.withOpacity(0.15),
                              VajraTheme.primaryPurple.withOpacity(0.0),
                            ],
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIndicatorTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 9,
          color: Color(0xFFF1F5F9),
          fontWeight: FontWeight.bold,
          fontFamily: 'monospace',
        ),
      ),
    );
  }
}
