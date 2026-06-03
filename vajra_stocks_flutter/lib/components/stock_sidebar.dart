import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../store/stock_provider.dart';

class StockSidebar extends ConsumerStatefulWidget {
  const StockSidebar({super.key});

  @override
  ConsumerState<StockSidebar> createState() => _StockSidebarState();
}

class _StockSidebarState extends ConsumerState<StockSidebar> {
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final stockState = ref.watch(stockProvider);
    final notifier = ref.read(stockProvider.notifier);

    final filteredSymbols = stockState.symbols.where((s) {
      final query = _searchQuery.toUpperCase().trim();
      if (query.isEmpty) return true;
      return s.symbol.toUpperCase().contains(query) ||
          s.companyName.toUpperCase().contains(query);
    }).toList();

    return Container(
      width: 260,
      decoration: const BoxDecoration(
        color: Color(0xFF0D0F14),
        border: Border(
          right: BorderSide(color: Color(0xFF1E293B), width: 0.8),
        ),
      ),
      child: Column(
        children: [
          // Search Header
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: TextField(
              controller: _searchController,
              onChanged: (val) => setState(() => _searchQuery = val),
              style: const TextStyle(fontSize: 13, color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Search stock, ISIN...',
                hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                prefixIcon: const Icon(Icons.search, size: 18, color: Color(0xFF94A3B8)),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 16),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
                filled: true,
                fillColor: const Color(0xFF07080A),
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
          
          // Virtualized List
          Expanded(
            child: filteredSymbols.isEmpty
                ? const Center(
                    child: Text(
                      'No tickers found.',
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    itemCount: filteredSymbols.length,
                    itemBuilder: (context, index) {
                      final s = filteredSymbols[index];
                      final isSelected = stockState.activeSymbol == s.symbol;
                      final isSynced = s.lastAttemptStatus == 'SUCCESS';

                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2.0),
                        child: InkWell(
                          onTap: () => notifier.setSelectedSymbol(s.symbol),
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? const Color(0xFF7C3AED).withOpacity(0.08)
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: isSelected
                                    ? const Color(0xFF7C3AED).withOpacity(0.3)
                                    : Colors.transparent,
                                width: 0.8,
                              ),
                            ),
                            child: Row(
                              children: [
                                // Ticker details
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            s.symbol.replaceFirst('.NS', ''),
                                            style: TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.bold,
                                              color: isSelected
                                                  ? Colors.white
                                                  : const Color(0xFFF1F5F9),
                                            ),
                                          ),
                                          const SizedBox(width: 6),
                                          Container(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 4,
                                              vertical: 1,
                                            ),
                                            decoration: BoxDecoration(
                                              color: const Color(0xFF07080A),
                                              border: Border.all(
                                                color: const Color(0xFF1E293B),
                                              ),
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              s.series,
                                              style: const TextStyle(
                                                fontSize: 8,
                                                color: Color(0xFF94A3B8),
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        s.companyName,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          fontSize: 11,
                                          color: Color(0xFF94A3B8),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                // Synced Dot Indicator
                                Container(
                                  width: 6,
                                  height: 6,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: isSynced
                                        ? const Color(0xFF34D399)
                                        : const Color(0xFFF87171),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
