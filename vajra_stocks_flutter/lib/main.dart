import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'theme/vajra_theme.dart';
import 'store/stock_provider.dart';
import 'widgets/responsive_layout.dart';
import 'components/stock_sidebar.dart';
import 'components/price_chart.dart';
import 'components/metrics_table.dart';
import 'components/corporate_timeline.dart';
import 'components/screener_panel.dart';
import 'components/sync_panel.dart';
import 'components/agent_terminal.dart';
import 'components/settings_panel.dart';

void main() {
  runApp(
    const ProviderScope(
      child: VajraStocksApp(),
    ),
  );
}

class VajraStocksApp extends StatelessWidget {
  const VajraStocksApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Vajra Stocks - Quant Platform',
      theme: VajraTheme.darkThemeData,
      debugShowCheckedModeBanner: false,
      home: const MainShellScaffold(),
    );
  }
}

class MainShellScaffold extends ConsumerStatefulWidget {
  const MainShellScaffold({super.key});

  @override
  ConsumerState<MainShellScaffold> createState() => _MainShellScaffoldState();
}

class _MainShellScaffoldState extends ConsumerState<MainShellScaffold> {
  @override
  void initState() {
    super.initState();
    // Initial bootstrap: fetch symbol list from ground truth DB
    Future.microtask(() => ref.read(stockProvider.notifier).fetchSymbols());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(stockProvider);

    return Scaffold(
      body: ResponsiveLayout(
        mobileBody: _buildMobileBody(state),
        tabletBody: _buildTabletBody(state),
        desktopBody: _buildDesktopBody(state),
      ),
    );
  }

  // --- MOBILE VIEW LAYOUT ---
  Widget _buildMobileBody(StockState state) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('VAJRA STOCKS'),
        actions: [
          if (state.isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16.0),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
      ),
      drawer: state.activeTab == 'explorer' ? const Drawer(child: StockSidebar()) : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _getTabIndex(state.activeTab),
        onDestinationSelected: (idx) => _onTabSelected(idx),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.show_chart), label: 'Explorer'),
          NavigationDestination(icon: Icon(Icons.filter_alt), label: 'Screener'),
          NavigationDestination(icon: Icon(Icons.sync), label: 'Sync'),
          NavigationDestination(icon: Icon(Icons.psychology), label: 'AI Agent'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
      body: _getActivePanel(state.activeTab),
    );
  }

  // --- TABLET VIEW LAYOUT ---
  Widget _buildTabletBody(StockState state) {
    return Scaffold(
      body: Row(
        children: [
          // Vertical Navigation Rail
          NavigationRail(
            selectedIndex: _getTabIndex(state.activeTab),
            onDestinationSelected: (idx) => _onTabSelected(idx),
            labelType: NavigationRailLabelType.all,
            backgroundColor: VajraTheme.darkCard,
            selectedIconTheme: const IconThemeData(color: Colors.white),
            unselectedIconTheme: const IconThemeData(color: Color(0xFF94A3B8)),
            selectedLabelTextStyle: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
            unselectedLabelTextStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10),
            destinations: const [
              NavigationRailDestination(icon: Icon(Icons.show_chart), label: Text('Explorer')),
              NavigationRailDestination(icon: Icon(Icons.filter_alt), label: Text('Screener')),
              NavigationRailDestination(icon: Icon(Icons.sync), label: Text('Sync')),
              NavigationRailDestination(icon: Icon(Icons.psychology), label: Text('AI Agent')),
              NavigationRailDestination(icon: Icon(Icons.settings), label: Text('Settings')),
            ],
          ),
          
          // Main panel view
          Expanded(
            child: _getActivePanel(state.activeTab),
          ),
        ],
      ),
    );
  }

  // --- DESKTOP VIEW LAYOUT ---
  Widget _buildDesktopBody(StockState state) {
    return Scaffold(
      body: Row(
        children: [
          // Collapsible Left Sidebar Navigation Drawer
          Container(
            width: 200,
            decoration: const BoxDecoration(
              color: VajraTheme.darkCard,
              border: Border(
                right: BorderSide(color: Color(0xFF1E293B), width: 0.8),
              ),
            ),
            child: Column(
              children: [
                // Top Brand Banner
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24.0, horizontal: 16.0),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: VajraTheme.primaryPurple.withOpacity(0.1),
                          border: Border.all(color: VajraTheme.primaryPurple.withOpacity(0.3)),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.auto_graph, color: VajraTheme.primaryPurple, size: 16),
                      ),
                      const SizedBox(width: 10),
                      const Text(
                        'VAJRA STOCKS',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                          color: Colors.white,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
                
                // Tabs list
                _buildDesktopTabTile(state, 'explorer', Icons.show_chart, 'Explorer'),
                _buildDesktopTabTile(state, 'screener', Icons.filter_alt, 'Screener Grid'),
                _buildDesktopTabTile(state, 'sync', Icons.sync, 'Sync Center'),
                _buildDesktopTabTile(state, 'ai-research', Icons.psychology, 'AI Console'),
                _buildDesktopTabTile(state, 'settings', Icons.settings, 'Settings'),
                
                const Spacer(),
                const Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text(
                    'Ver 1.0.0 (Native)',
                    style: TextStyle(fontSize: 10, color: Color(0xFF94A3B8), fontFamily: 'monospace'),
                  ),
                ),
              ],
            ),
          ),
          
          // Main Panel View
          Expanded(
            child: _getActivePanel(state.activeTab),
          ),
        ],
      ),
    );
  }

  Widget _buildDesktopTabTile(StockState state, String tabKey, IconData icon, String title) {
    final isSelected = state.activeTab == tabKey;
    final notifier = ref.read(stockProvider.notifier);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 4.0),
      child: InkWell(
        onTap: () => notifier.setActiveTab(tabKey),
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? VajraTheme.primaryPurple.withOpacity(0.1) : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? VajraTheme.primaryPurple.withOpacity(0.2) : Colors.transparent,
            ),
          ),
          child: Row(
            children: [
              Icon(icon, size: 16, color: isSelected ? Colors.white : const Color(0xFF94A3B8)),
              const SizedBox(width: 10),
              Text(
                title,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  color: isSelected ? Colors.white : const Color(0xFF94A3B8),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  int _getTabIndex(String tab) {
    switch (tab) {
      case 'explorer':
        return 0;
      case 'screener':
        return 1;
      case 'sync':
        return 2;
      case 'ai-research':
        return 3;
      case 'settings':
        return 4;
      default:
        return 0;
    }
  }

  void _onTabSelected(int idx) {
    final notifier = ref.read(stockProvider.notifier);
    switch (idx) {
      case 0:
        notifier.setActiveTab('explorer');
        break;
      case 1:
        notifier.setActiveTab('screener');
        break;
      case 2:
        notifier.setActiveTab('sync');
        break;
      case 3:
        notifier.setActiveTab('ai-research');
        break;
      case 4:
        notifier.setActiveTab('settings');
        break;
    }
  }

  Widget _getActivePanel(String tab) {
    switch (tab) {
      case 'explorer':
        return _buildExplorerWorkspace();
      case 'screener':
        return const ScreenerPanel();
      case 'sync':
        return const SyncPanel();
      case 'ai-research':
        return const AgentTerminal();
      case 'settings':
        return const SettingsPanel();
      default:
        return _buildExplorerWorkspace();
    }
  }

  Widget _buildExplorerWorkspace() {
    return ResponsiveLayout(
      mobileBody: const _MobileExplorerView(),
      tabletBody: const _TabletExplorerView(),
      desktopBody: const _DesktopExplorerView(),
    );
  }
}

// --- EXPLORER SUB-VIEWS ---
class _MobileExplorerView extends ConsumerWidget {
  const _MobileExplorerView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    if (state.activeSymbolDetail == null) {
      return const Center(
        child: Text('Select a ticker from Drawer to begin.'),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          _buildExplorerHeader(state, ref),
          const SizedBox(height: 12),
          const StockPriceChart(indicatorToShow: 'RSI'),
          const SizedBox(height: 12),
          const MetricsTable(),
          const SizedBox(height: 12),
          const CorporateActionsTimeline(),
        ],
      ),
    );
  }
}

class _TabletExplorerView extends ConsumerWidget {
  const _TabletExplorerView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    return Row(
      children: [
        const StockSidebar(),
        Expanded(
          child: state.activeSymbolDetail == null
              ? const Center(child: Text('Select an active stock ticker to analyze.'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _buildExplorerHeader(state, ref),
                      const SizedBox(height: 16),
                      const StockPriceChart(indicatorToShow: 'RSI'),
                      const SizedBox(height: 16),
                      const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 6, child: MetricsTable()),
                          SizedBox(width: 16),
                          Expanded(flex: 4, child: CorporateActionsTimeline()),
                        ],
                      ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}

class _DesktopExplorerView extends ConsumerWidget {
  const _DesktopExplorerView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(stockProvider);

    return Row(
      children: [
        const StockSidebar(),
        Expanded(
          child: state.activeSymbolDetail == null
              ? const Center(child: Text('Select an active stock ticker to analyze.'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      _buildExplorerHeader(state, ref),
                      const SizedBox(height: 20),
                      const StockPriceChart(indicatorToShow: 'RSI'),
                      const SizedBox(height: 20),
                      const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 7, child: MetricsTable()),
                          SizedBox(width: 20),
                          Expanded(flex: 3, child: CorporateActionsTimeline()),
                        ],
                      ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}

Widget _buildExplorerHeader(StockState state, WidgetRef ref) {
  final d = state.activeSymbolDetail!;
  final notifier = ref.read(stockProvider.notifier);

  return Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: VajraTheme.darkCard,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: const Color(0xFF1E293B)),
    ),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  d.symbol.replaceFirst('.NS', ''),
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                  decoration: BoxDecoration(
                    color: const Color(0xFF07080A),
                    border: Border.all(color: const Color(0xFF1E293B)),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    d.series,
                    style: const TextStyle(fontSize: 8, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(d.companyName, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
          ],
        ),
        
        // Chart Type Selector
        Row(
          children: [
            const Text('Chart style: ', style: TextStyle(fontSize: 10, color: Color(0xFF94A3B8))),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                color: const Color(0xFF07080A),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFF1E293B)),
              ),
              child: Row(
                children: ['candles', 'heikin-ashi', 'renko'].map((style) {
                  final isSel = state.chartType == style;
                  return InkWell(
                    onTap: () => notifier.setChartType(style),
                    borderRadius: BorderRadius.circular(4),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: isSel ? VajraTheme.primaryPurple : Colors.transparent,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        style.toUpperCase(),
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          color: isSel ? Colors.white : const Color(0xFF94A3B8),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ],
    ),
  );
}
