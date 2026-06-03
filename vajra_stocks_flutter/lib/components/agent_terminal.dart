import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';

class AgentTerminal extends ConsumerStatefulWidget {
  const AgentTerminal({super.key});

  @override
  ConsumerState<AgentTerminal> createState() => _AgentTerminalState();
}

class _AgentTerminalState extends ConsumerState<AgentTerminal> {
  final TextEditingController _promptController = TextEditingController();
  final ScrollController _terminalScrollController = ScrollController();

  @override
  void dispose() {
    _promptController.dispose();
    _terminalScrollController.dispose();
    super.dispose();
  }

  void _submitPrompt(String query) {
    if (query.isEmpty) return;
    _promptController.clear();
    ref.read(stockProvider.notifier).runAiWorkflow(query);
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_terminalScrollController.hasClients) {
        _terminalScrollController.animateTo(
          _terminalScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(stockProvider);
    
    // Automatically scroll console log on new events
    if (state.aiEvents.isNotEmpty) {
      _scrollToBottom();
    }

    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Title Header Banner
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI Research Console',
                      style: VajraTheme.darkThemeData.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Trigger compiled multi-agent workflows and inspect qualitative trend interpretations.',
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                    ),
                  ],
                ),
                if (state.aiReport != null)
                  ElevatedButton.icon(
                    onPressed: () => ref.read(stockProvider.notifier).clearAiConsole(),
                    icon: const Icon(Icons.clear_all, size: 16),
                    label: const Text('Clear Console'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF1E293B),
                      foregroundColor: Colors.white,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // Dynamic view panels (Console / Report split)
            Expanded(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // LEFT: Live SSE Progress Event Console
                  Expanded(
                    flex: 4,
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Qualitative Agent Streaming Logs',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                            ),
                            const Divider(color: Color(0xFF1E293B), height: 24),
                            Expanded(
                              child: state.aiEvents.isEmpty
                                  ? _buildPresetsPane()
                                  : Container(
                                      padding: const EdgeInsets.all(12),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF07080A),
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: const Color(0xFF1E293B)),
                                      ),
                                      child: ListView.builder(
                                        controller: _terminalScrollController,
                                        itemCount: state.aiEvents.length,
                                        itemBuilder: (context, index) {
                                          final e = state.aiEvents[index];
                                          final eventName = e['event'];
                                          final eventData = e['data'];

                                          return Padding(
                                            padding: const EdgeInsets.symmetric(vertical: 4.0),
                                            child: Text(
                                              '[$eventName] ${eventData.toString()}',
                                              style: const TextStyle(
                                                fontFamily: 'monospace',
                                                fontSize: 11,
                                                color: Color(0xFF34D399),
                                              ),
                                            ),
                                          );
                                        },
                                      ),
                                    ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),

                  // RIGHT: Final Markdown qualitative investment report
                  Expanded(
                    flex: 6,
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Investment / Breakdown Report',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                ),
                                if (state.aiRecommendation != null)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: VajraTheme.primaryPurple.withOpacity(0.15),
                                      borderRadius: BorderRadius.circular(4),
                                      border: Border.all(color: VajraTheme.primaryPurple),
                                    ),
                                    child: Text(
                                      '${state.aiRecommendation} (${state.aiConfidence})',
                                      style: const TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                            const Divider(color: Color(0xFF1E293B), height: 24),
                            Expanded(
                              child: state.aiReport == null
                                  ? Center(
                                      child: Text(
                                        state.aiIsLoading
                                            ? 'Compiling quantitative variables. Please wait...'
                                            : 'Start a quantitative workflow to generate reports.',
                                        style: const TextStyle(color: Color(0xFF94A3B8)),
                                      ),
                                    )
                                  : Markdown(
                                      data: state.aiReport!,
                                      styleSheet: MarkdownStyleSheet.fromTheme(
                                        VajraTheme.darkThemeData,
                                      ).copyWith(
                                        p: const TextStyle(height: 1.6, fontSize: 13, color: Color(0xFFF1F5F9)),
                                        h1: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                                        h2: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.white),
                                        h3: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white),
                                        tableBorder: TableBorder.all(color: const Color(0xFF1E293B), width: 0.8),
                                        tableCellsPadding: const EdgeInsets.all(8.0),
                                        tableHead: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
                                        tableBody: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                                      ),
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
            const SizedBox(height: 16),

            // Prompt input bar
            Row(
              children: [
                Expanded(
                  child: SizedBox(
                    height: 44,
                    child: TextField(
                      controller: _promptController,
                      onSubmitted: _submitPrompt,
                      style: const TextStyle(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: 'Enter stock query (e.g. "Analyze TCS", "Momentum Breakout Scan")...',
                        hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                        fillColor: const Color(0xFF0D0F14),
                        filled: true,
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: Color(0xFF1E293B)),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: Color(0xFF7C3AED)),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: state.aiIsLoading
                      ? null
                      : () => _submitPrompt(_promptController.text),
                  icon: const Icon(Icons.send, size: 14),
                  label: const Text('Execute'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: VajraTheme.primaryPurple,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(120, 44),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPresetsPane() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Select a quick-start quantitative workflow preset card:',
          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        const SizedBox(height: 12),
        _buildPresetCard(
          'Momentum Breakout Scan',
          'Execute high-speed multi-ticker filters to flag strong trend crossovers.',
          'Find breakout opportunities',
        ),
        const SizedBox(height: 8),
        _buildPresetCard(
          'Macro Market Regime Audit',
          'Inspect systematic index metrics and classify macro volatility regimes.',
          'Market status',
        ),
        const SizedBox(height: 8),
        _buildPresetCard(
          'Single-Stock Trend deep-dive',
          'Initiate ATR stops, position sizing math, and qualitative setup interpreting.',
          'Analyze TCS.NS',
        ),
      ],
    );
  }

  Widget _buildPresetCard(String title, String description, String query) {
    return InkWell(
      onTap: () => _submitPrompt(query),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF07080A),
          border: Border.all(color: const Color(0xFF1E293B)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.white),
            ),
            const SizedBox(height: 4),
            Text(
              description,
              style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8)),
            ),
          ],
        ),
      ),
    );
  }
}
