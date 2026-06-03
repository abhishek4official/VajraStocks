import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';

class CorporateActionsTimeline extends ConsumerWidget {
  const CorporateActionsTimeline({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    if (state.corporateActions.isEmpty) {
      return const SizedBox(
        height: 260,
        child: Card(
          child: Center(
            child: Padding(
              padding: EdgeInsets.all(16.0),
              child: Text(
                'No splits or dividends recorded.',
                style: TextStyle(color: Color(0xFF94A3B8)),
              ),
            ),
          ),
        ),
      );
    }

    final recentActions = state.corporateActions.length > 5
        ? state.corporateActions.sublist(state.corporateActions.length - 5).reversed.toList()
        : state.corporateActions.reversed.toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Corporate Actions History',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
            const SizedBox(height: 16),
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: recentActions.length,
              itemBuilder: (context, index) {
                final action = recentActions[index];
                final isSplit = action.actionType == 'SPLIT';

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Timeline nodes/line
                    Column(
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: isSplit ? Colors.amber : VajraTheme.primaryPurple,
                          ),
                        ),
                        if (index < recentActions.length - 1)
                          Container(
                            width: 1.5,
                            height: 48,
                            color: const Color(0xFF1E293B),
                          ),
                      ],
                    ),
                    const SizedBox(width: 16),
                    
                    // Detail Text
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                action.actionType,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: isSplit ? Colors.amber : const Color(0xFFA78BFA),
                                ),
                              ),
                              Text(
                                DateFormat('dd-MM-yyyy').format(action.actionDate),
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: Color(0xFF94A3B8),
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            isSplit
                                ? 'Stock Split ratio: 1 : ${action.value.toStringAsFixed(0)}'
                                : 'Dividend payout: ₹${action.value.toStringAsFixed(2)} per share',
                            style: const TextStyle(fontSize: 12, color: Color(0xFFF1F5F9)),
                          ),
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
