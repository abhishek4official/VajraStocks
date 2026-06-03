import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../store/stock_provider.dart';
import '../theme/vajra_theme.dart';
import '../services/api_service.dart';

class SettingsPanel extends ConsumerStatefulWidget {
  const SettingsPanel({super.key});

  @override
  ConsumerState<SettingsPanel> createState() => _SettingsPanelState();
}

class _SettingsPanelState extends ConsumerState<SettingsPanel> {
  final TextEditingController _urlController = TextEditingController();
  bool _isTesting = false;
  String? _testResult;
  bool _testSuccess = false;
  int? _testLatency;
  Map<String, dynamic>? _serverInfo;

  @override
  void initState() {
    super.initState();
    // Pre-populate with current state base URL
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final state = ref.read(stockProvider);
      _urlController.text = state.baseUrl;
      _testConnection(state.baseUrl);
    });
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _testConnection(String url) async {
    setState(() {
      _isTesting = true;
      _testResult = 'Testing connection...';
      _testSuccess = false;
      _testLatency = null;
      _serverInfo = null;
    });

    try {
      final testService = ApiService(baseUrl: url);
      final info = await testService.checkHealth();
      setState(() {
        _isTesting = false;
        _testSuccess = true;
        _testLatency = info['latency_ms'];
        _serverInfo = info;
        _testResult = 'Connection successful!';
      });
    } catch (e) {
      setState(() {
        _isTesting = false;
        _testSuccess = false;
        _testResult = 'Connection failed. Verify host port and server status.';
        _serverInfo = null;
      });
    }
  }

  void _saveAndApply(String url) {
    ref.read(stockProvider.notifier).updateBaseUrl(url);
    _testConnection(url);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('API Base URL updated to: $url'),
        backgroundColor: VajraTheme.primaryPurple,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      body: SingleChildScrollView(
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
                      'System Configuration Settings',
                      style: VajraTheme.darkThemeData.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Manage connections, custom endpoints, and diagnose system resolution discrepancies.',
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Diagnostic Alert Card (Windows IPv6 / CORS Explanation)
            Card(
              color: const Color(0xFF1E1B4B),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline, color: Color(0xFFA78BFA), size: 22),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Windows IPv6 / localhost Loopback Diagnostic',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
                          ),
                          const SizedBox(height: 6),
                          const Text(
                            'In Windows environments, Flutter occasionally resolves "localhost" to IPv6 loopback [::1], whereas the backend server (FastAPI) listens explicitly on IPv4 (127.0.0.1). If your dashboard is not hitting anything and shows connection errors, we highly recommend switching the Base URL to http://127.0.0.1:8000.',
                            style: TextStyle(color: Color(0xFFC7D2FE), fontSize: 11, height: 1.4),
                          ),
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 8,
                            children: [
                              ActionChip(
                                label: const Text('Use http://127.0.0.1:8000 (IPv4)', style: TextStyle(fontSize: 10)),
                                backgroundColor: const Color(0xFF312E81),
                                labelStyle: const TextStyle(color: Color(0xFFE0E7FF)),
                                onPressed: () {
                                  _urlController.text = 'http://127.0.0.1:8000';
                                  _saveAndApply('http://127.0.0.1:8000');
                                },
                              ),
                              ActionChip(
                                label: const Text('Use http://localhost:8000 (Default)', style: TextStyle(fontSize: 10)),
                                backgroundColor: const Color(0xFF312E81),
                                labelStyle: const TextStyle(color: Color(0xFFE0E7FF)),
                                onPressed: () {
                                  _urlController.text = 'http://localhost:8000';
                                  _saveAndApply('http://localhost:8000');
                                },
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Settings Fields Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'FastAPI Service Connection Endpoints',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                    const Divider(color: Color(0xFF1E293B), height: 24),
                    const SizedBox(height: 4),
                    const Text(
                      'API BASE URL',
                      style: TextStyle(fontSize: 10, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: SizedBox(
                            height: 44,
                            child: TextField(
                              controller: _urlController,
                              style: const TextStyle(fontSize: 13, fontFamily: 'monospace'),
                              decoration: InputDecoration(
                                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                                fillColor: const Color(0xFF07080A),
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
                          onPressed: () => _saveAndApply(_urlController.text),
                          icon: const Icon(Icons.check, size: 14),
                          label: const Text('Save & Apply'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: VajraTheme.primaryPurple,
                            foregroundColor: Colors.white,
                            minimumSize: const Size(140, 44),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        OutlinedButton.icon(
                          onPressed: () => _testConnection(_urlController.text),
                          icon: _isTesting
                              ? const SizedBox(
                                  width: 12,
                                  height: 12,
                                  child: CircularProgressIndicator(strokeWidth: 1.5, color: Colors.white),
                                )
                              : const Icon(Icons.network_ping, size: 14),
                          label: const Text('Test Connection Endpoint'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: const BorderSide(color: Color(0xFF1E293B)),
                            minimumSize: const Size(180, 40),
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
            ),
            const SizedBox(height: 20),

            // Live Diagnostics Results Card
            if (_testResult != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Active Endpoint Connection Diagnostics',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const Divider(color: Color(0xFF1E293B), height: 24),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: _testSuccess
                                  ? VajraTheme.accentGreen.withValues(alpha: 0.1)
                                  : VajraTheme.accentRed.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              _testSuccess ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                              color: _testSuccess ? VajraTheme.accentGreen : VajraTheme.accentRed,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  _testSuccess ? 'ONLINE / CONNECTED' : 'OFFLINE / UNREACHABLE',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                    color: _testSuccess ? VajraTheme.accentGreen : VajraTheme.accentRed,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _testResult!,
                                  style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                                ),
                              ],
                            ),
                          ),
                          if (_testSuccess && _testLatency != null)
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                const Text(
                                  'LATENCY',
                                  style: TextStyle(fontSize: 9, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${_testLatency}ms',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontFamily: 'monospace',
                                    fontWeight: FontWeight.bold,
                                    color: _testLatency! < 50
                                        ? VajraTheme.accentGreen
                                        : _testLatency! < 150
                                            ? Colors.amber
                                            : VajraTheme.accentRed,
                                  ),
                                ),
                              ],
                            ),
                        ],
                      ),
                      if (_testSuccess && _serverInfo != null) ...[
                        const SizedBox(height: 16),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xFF07080A),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFF1E293B)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'SERVER METADATA PAYLOAD',
                                style: TextStyle(fontSize: 9, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 8),
                              _buildMetadataRow('System status', _serverInfo!['status'] ?? 'N/A'),
                              _buildMetadataRow('Service Application', _serverInfo!['app_name'] ?? 'N/A'),
                              _buildMetadataRow('Active Environment', _serverInfo!['environment'] ?? 'N/A'),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetadataRow(String key, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3.0),
      child: Row(
        children: [
          Text('$key: ', style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
          Text(value, style: const TextStyle(fontSize: 11, color: Colors.white, fontFamily: 'monospace')),
        ],
      ),
    );
  }
}
