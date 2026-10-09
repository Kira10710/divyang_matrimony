import 'package:divyang_matrimony/features/auth/presentation/providers/auth_provider.dart';
import 'package:divyang_matrimony/features/auth/presentation/screens/welcome_screen.dart';
import 'package:divyang_matrimony/features/profile/presentation/screens/profile_wizard_screen.dart';
import 'package:divyang_matrimony/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(
  WidgetTester tester,
  Widget screen, {
  Size size = const Size(1280, 2600),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [currentUserProvider.overrideWith((Ref ref) => null)],
      child: MaterialApp(theme: AppTheme.light(), home: screen),
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
  testWidgets(
    'landing registration card requires a name and a valid mobile number',
    (WidgetTester tester) async {
      await _pump(tester, const WelcomeScreen(), size: const Size(1440, 4000));

      await _tapText(tester, 'REGISTER FREE');

      expect(find.text('Enter a name'), findsOneWidget);
      expect(find.text('Enter your phone number'), findsOneWidget);
    },
  );

  testWidgets(
    'profile wizard cannot pass the disability step without type and onset',
    (WidgetTester tester) async {
      await _pump(tester, const ProfileWizardScreen());

      // Step 1 — basics are validated first.
      await _tapText(tester, 'Continue');
      expect(find.text('Enter the first name'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextFormField, 'First name *'),
        'Priya',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Last name *'),
        'Sharma',
      );
      await _tapText(tester, 'Female');
      await tester.tap(find.widgetWithText(TextFormField, 'Date of birth *'));
      await tester.pumpAndSettle();
      await _tapText(tester, 'OK');
      await _tapText(tester, 'Never married');
      await _tapText(tester, 'Continue');

      // Step 2 — disability is mandatory.
      expect(find.text('About your disability'), findsOneWidget);
      await _tapText(tester, 'Continue');
      expect(find.text('Please choose the type of disability'), findsOneWidget);
      expect(find.text('Please choose one'), findsOneWidget);
      expect(find.text('About your disability'), findsOneWidget);

      await _tapText(tester, 'Visual');
      await _tapText(tester, 'Since birth');
      await _tapText(tester, 'Continue');

      expect(
        find.text('Religion and caste are shown only to premium members.'),
        findsOneWidget,
      );
    },
  );
}
