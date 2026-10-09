import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../theme/app_theme.dart';
import '../../../profile/presentation/providers/registration_draft_provider.dart';
import '../widgets/landing/landing_hero.dart';
import '../widgets/landing/landing_sections.dart';
import '../widgets/landing/quick_search_bar.dart';
import '../widgets/landing/registration_card.dart';

/// Logged-out landing page — the canonical destination
/// `routing/guards/auth_guard.dart` sends any unauthenticated visitor to.
///
/// Registration and login share one backend entry point
/// (`POST /auth/send-otp`); the card here collects just enough to start
/// (who it's for, a name, a mobile number) and the profile wizard asks the
/// rest — including disability details — after OTP.
class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  static const List<String> _featuredLanguages = <String>[
    'Hindi',
    'Marathi',
    'Gujarati',
    'Bengali',
    'Tamil',
    'Telugu',
    'Kannada',
    'Malayalam',
    'Punjabi',
    'Odia',
    'Urdu',
    'Marwari',
  ];

  final GlobalKey _cardKey = GlobalKey();
  final FocusNode _nameFocus = FocusNode();

  @override
  void dispose() {
    _nameFocus.dispose();
    super.dispose();
  }

  Future<void> _goToRegistration() async {
    final BuildContext? cardContext = _cardKey.currentContext;
    if (cardContext != null) {
      await Scrollable.ensureVisible(
        cardContext,
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeInOut,
        alignment: 0.1,
      );
    }
    _nameFocus.requestFocus();
  }

  void _pickLanguage(String language) {
    ref
        .read(registrationDraftProvider.notifier)
        .update((RegistrationDraft d) => d.copyWith(motherTongue: language));
    _goToRegistration();
  }

  @override
  Widget build(BuildContext context) {
    // The landing page is a brand surface with fixed light section colours,
    // so it always renders in the light theme; signed-in screens follow the
    // system setting.
    return Theme(
      data: AppTheme.light(),
      child: Scaffold(
        body: SafeArea(
          child: Column(
            children: <Widget>[
              const LandingTopBar(),
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: <Widget>[
                      LandingHero(
                        registrationCard: RegistrationCard(
                          key: _cardKey,
                          nameFocusNode: _nameFocus,
                        ),
                        quickSearch: QuickSearchBar(onBegin: _goToRegistration),
                      ),
                      const TrustStrip(),
                      const HowItWorksSection(),
                      const PrivacyLadderSection(),
                      const FeaturesSection(),
                      LanguageStrip(
                        languages: _featuredLanguages,
                        onPick: _pickLanguage,
                      ),
                      ClosingCta(onRegister: _goToRegistration),
                      const LandingFooter(),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
