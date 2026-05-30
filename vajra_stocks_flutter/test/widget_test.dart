import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:vajra_stocks_flutter/main.dart';

void main() {
  testWidgets('App renders main scaffold without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: VajraStocksApp(),
      ),
    );

    // Verify if VajraStocksApp renders.
    expect(find.byType(VajraStocksApp), findsOneWidget);
  });
}
