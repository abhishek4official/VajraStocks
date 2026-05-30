import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';

class SyncPanel extends ConsumerStatefulWidget {
  const SyncPanel({super.key});

  @override
  ConsumerState<SyncPanel> createState() => _SyncPanelState();
}

class _SyncPanelState extends ConsumerState<SyncPanel> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(stockProvider.notifier).fetchSyncLogs());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(stockProvider);
    final notifier = ref.read(stockProvider.notifier);

    final String statusStr = state.syncStatuses['status'] ?? 'IDLE';
    final int pending = state.syncStatuses['pending_symbols'] ?? 0;
    final int failed = state.syncStatuses['failed_symbols'] ?? 0;
    final int synced = state.syncStatuses['synced_symbols'] ?? 0;

    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Banner
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Synchronization Control Center',
                      style: VajraTheme.darkThemeData.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Manage EOD historical downloads and monitor indicators calculation pipelines.',
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                    ),
                  ],
                ),
                Row(
                  children: [
                    ElevatedButton.icon(
                      onPressed: state.isSyncing ? null : () => notifier.fetchSyncLogs(),
                      icon: const Icon(Icons.refresh, size: 16),
                      label: const Text('Refresh Logs'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1E293B),
                        foregroundColor: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton.icon(
                      onPressed: state.isSyncing ? null : () => notifier.triggerSync(),
                      icon: const Icon(Icons.sync, size: 16),
                      label: const Text('Sync EOD Data'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: VajraTheme.primaryPurple,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Sync Status Metrics Cards
            Row(
              children: [
                Expanded(
                  child: _buildMetricCard(
                    'ENGINE STATUS',
                    statusStr,
                    statusStr == 'RUNNING' ? VajraTheme.primaryPurple : const Color(0xFF94A3B8),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(child: _buildMetricCard('SYNCED', '$synced symbols', VajraTheme.accentGreen)),
                const SizedBox(width: 12),
                Expanded(child: _buildMetricCard('PENDING', '$pending symbols', Colors.amber)),
                const SizedBox(width: 12),
                Expanded(child: _buildMetricCard('FAILED / WARNING', '$failed symbols', VajraTheme.accentRed)),
              ],
            ),
            const SizedBox(height: 20),

            // Triage Failure Logs
            Expanded(
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Recent Synchronization Runs Audit Logs',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: state.syncJobs.isEmpty
                            ? const Center(
                                child: Text(
                                  'No sync job history recorded in the database.',
                                  style: TextStyle(color: Color(0xFF94A3B8)),
                                ),
                              )
                            : ListView.separated(
                                itemCount: state.syncJobs.length,
                                separatorBuilder: (context, index) => const Divider(color: Color(0xFF1E293B)),
                                itemBuilder: (context, index) {
                                  final job = state.syncJobs[index];
                                  final isSuccess = job.status == 'SUCCESS';
                                  final isPartial = job.status == 'PARTIAL';

                                  return ListTile(
                                    contentPadding: EdgeInsets.zero,
                                    title: Row(
                                      children: [
                                        Text(
                                          'Run ID: ${job.runId.substring(0, 8)}',
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                        ),
                                        const SizedBox(width: 12),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: isSuccess
                                                ? VajraTheme.accentGreen.withOpacity(0.1)
                                                : isPartial
                                                    ? Colors.amber.withOpacity(0.1)
                                                    : VajraTheme.accentRed.withOpacity(0.1),
                                            borderRadius: BorderRadius.circular(4),
                                          ),
                                          child: Text(
                                            job.status,
                                            style: TextStyle(
                                              fontSize: 9,
                                              fontWeight: FontWeight.bold,
                                              color: isSuccess
                                                  ? VajraTheme.accentGreen
                                                  : isPartial
                                                      ? Colors.amber
                                                      : VajraTheme.accentRed,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                    subtitle: Padding(
                                      padding: const EdgeInsets.only(top: 6.0),
                                      child: Text(
                                        'Processed: ${job.processedSymbols}/${job.totalSymbols} | Failed: ${job.failedSymbols} | Records Added: ${job.recordsInserted}\n'
                                        'Started: ${DateFormat('dd-MM-yyyy HH:mm:ss').format(job.startTime.toLocal())}',
                                        style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                                      ),
                                    ),
                                    trailing: job.errorSummary != null
                                        ? IconButton(
                                            icon: const Icon(Icons.info_outline, color: VajraTheme.accentRed),
                                            onPressed: () {
                                              showDialog(
                                                context: context,
                                                builder: (context) {
                                                  return AlertDialog(
                                                    backgroundColor: const Color(0xFF0D0F14),
                                                    title: const Text('Sync Run Failure Details'),
                                                    content: SingleChildScrollView(
                                                      child: Text(
                                                        job.errorSummary!,
                                                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                                                      ),
                                                    ),
                                                    actions: [
                                                      TextButton(
                                                        onPressed: () => Navigator.of(context).pop(),
                                                        child: const Text('Dismiss'),
                                                      ),
                                                    ],
                                                  );
                                                },
                                              );
                                            },
                                          )
                                        : null,
                                  );
                                },
                              ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0D0F14),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
