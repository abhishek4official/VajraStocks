import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/stock_models.dart';

class ApiService {
  String baseUrl;
  final http.Client client;

  ApiService({this.baseUrl = 'http://localhost:8000', http.Client? client})
      : client = client ?? http.Client();

  Future<Map<String, dynamic>> checkHealth() async {
    try {
      final stopwatch = Stopwatch()..start();
      final response = await client.get(
        Uri.parse('$baseUrl/health'),
      ).timeout(const Duration(seconds: 3));
      stopwatch.stop();
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = jsonDecode(response.body);
        data['latency_ms'] = stopwatch.elapsedMilliseconds;
        return data;
      }
      throw Exception('Server returned status code ${response.statusCode}');
    } catch (e) {
      throw Exception('Connection failed: $e');
    }
  }

  Future<List<StockSymbol>> getAllSymbols({bool activeOnly = true}) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/symbols/?active_only=$activeOnly'),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => StockSymbol.fromJson(json)).toList();
    }
    throw Exception('Failed to load symbols: ${response.statusCode}');
  }

  Future<StockSymbol> getSymbolDetail(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/symbols/$symbol'),
    );
    if (response.statusCode == 200) {
      return StockSymbol.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load symbol details: ${response.statusCode}');
  }

  Future<List<DailyPrice>> getCandles(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/charts/$symbol/candles'),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => DailyPrice.fromJson(json)).toList();
    }
    throw Exception('Failed to load candles: ${response.statusCode}');
  }

  Future<List<dynamic>> getHeikinAshi(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/charts/$symbol/heikin-ashi'),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load Heikin-Ashi: ${response.statusCode}');
  }

  Future<List<dynamic>> getRenkoBricks(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/charts/$symbol/renko'),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load Renko bricks: ${response.statusCode}');
  }

  Future<List<dynamic>> getLineBreakLines(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/charts/$symbol/line-break'),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load Line Break lines: ${response.statusCode}');
  }

  Future<List<TechnicalIndicator>> getIndicators(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/indicators/$symbol'),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => TechnicalIndicator.fromJson(json)).toList();
    }
    throw Exception('Failed to load indicators: ${response.statusCode}');
  }

  Future<List<CorporateAction>> getCorporateActions(String symbol) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/corporate-actions/$symbol'),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => CorporateAction.fromJson(json)).toList();
    }
    throw Exception('Failed to load corporate actions: ${response.statusCode}');
  }

  Future<List<ScreenerRow>> runScreener(Map<String, dynamic> filters) async {
    final response = await client.post(
      Uri.parse('$baseUrl/api/v1/screeners/run'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(filters),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => ScreenerRow.fromJson(json)).toList();
    }
    throw Exception('Failed to run screening sweep: ${response.statusCode}');
  }

  Future<List<SyncJob>> getSyncJobs({int limit = 20}) async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/sync/jobs?limit=$limit'),
    );
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => SyncJob.fromJson(json)).toList();
    }
    throw Exception('Failed to load sync jobs: ${response.statusCode}');
  }

  Future<List<dynamic>> getSyncStatus() async {
    final response = await client.get(
      Uri.parse('$baseUrl/api/v1/sync/status'),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load sync status: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> triggerFullSync() async {
    final response = await client.post(
      Uri.parse('$baseUrl/api/v1/sync/full'),
    );
    if (response.statusCode == 200 || response.statusCode == 202) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger sync: ${response.body}');
  }

  Future<Map<String, dynamic>> triggerSymbolSync(String symbol) async {
    final response = await client.post(
      Uri.parse('$baseUrl/api/v1/sync/symbol/$symbol'),
    );
    if (response.statusCode == 200 || response.statusCode == 202) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger symbol sync: ${response.body}');
  }

  Future<Map<String, dynamic>> triggerRecalculate({String? symbol}) async {
    final url = symbol != null
        ? '$baseUrl/api/v1/sync/recalculate?symbol=$symbol'
        : '$baseUrl/api/v1/sync/recalculate';
    final response = await client.post(Uri.parse(url));
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger recalculation: ${response.body}');
  }

  Stream<String> runAiWorkflowStream(String prompt) async* {
    final request = http.Request(
      'GET',
      Uri.parse('$baseUrl/api/v1/agents/chat-stream?prompt=${Uri.encodeQueryComponent(prompt)}'),
    );
    
    final response = await client.send(request);
    if (response.statusCode == 200) {
      final lines = response.stream.transform(utf8.decoder).transform(const LineSplitter());
      await for (final line in lines) {
        if (line.startsWith('data: ')) {
          yield line.substring(6);
        }
      }
    } else {
      throw Exception('Failed to establish AI Chat stream: ${response.statusCode}');
    }
  }
}
