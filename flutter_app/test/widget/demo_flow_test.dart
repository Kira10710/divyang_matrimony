import 'package:divyang_matrimony/app.dart';
import 'package:divyang_matrimony/config/env/env_config.dart';
import 'package:divyang_matrimony/config/env/flavor.dart';
import 'package:divyang_matrimony/demo/demo_mode.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

// Showcase flow. Run with:
//   flutter test test/widget/demo_flow_test.dart --dart-define=DEMO_MODE=true
// Without the flag the tests are skipped.

Future<void> _pumpApp(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1440, 4000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  EnvConfig.initialize(Flavor.prod);
  await tester.pumpWidget(
    ProviderScope(
      overrides: demoOverrides(),
      child: const DivyangMatrimonyApp(),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _tapText(WidgetTester tester, String text) async {
  await tester.ensureVisible(find.text(text).first);
  await tester.tap(find.text(text).first);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('landing shows the demo banner, not a signed-in screen', (
    WidgetTester tester,
  ) async {
    await _pumpApp(tester);
    expect(find.textContaining('DEMO PREVIEW'), findsOneWidget);
    expect(find.text('REGISTER FREE'), findsOneWidget);
  }, skip: !kDemoMode);

  testWidgets('registering with a valid name and number opens the dashboard', (
    WidgetTester tester,
  ) async {
    await _pumpApp(tester);
    await _tapText(tester, 'REGISTER FREE');
    expect(find.text('Enter a name'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Your full name'),
      'Priya Kapoor',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Mobile number'),
      '9876543210',
    );
    await _tapText(tester, 'REGISTER FREE');

    expect(find.textContaining('Namaste, Priya'), findsOneWidget);
    expect(find.text('Quick actions'), findsOneWidget);
  }, skip: !kDemoMode);

  testWidgets("\"Let's begin\" opens search results for the chosen filters", (
    WidgetTester tester,
  ) async {
    await _pumpApp(tester);
    await _tapText(tester, "Let's begin");
    expect(find.textContaining('matches'), findsOneWidget);
    expect(find.text('Send interest'), findsWidgets);
  }, skip: !kDemoMode);
}
