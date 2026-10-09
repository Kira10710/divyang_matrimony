import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/extensions/context_extensions.dart';
import '../../../../shared/widgets/accessible_button.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../shared/widgets/otp_input_field.dart';
import '../../../../shared/widgets/responsive_scaffold.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/login_provider.dart';

/// Step 2 of login/registration — verifies the OTP sent by
/// [LoginScreen] (`POST /auth/verify-otp`).
///
/// Reads the pending phone number out of [loginProvider] rather than a
/// route parameter, since that state already exists and is the single
/// source of truth for "which phone is this flow for."
class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key});

  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen> {
  static const int _resendCooldownSeconds = 60;

  Timer? _cooldownTimer;
  int _secondsRemaining = _resendCooldownSeconds;
  String _otp = '';

  @override
  void initState() {
    super.initState();
    _startCooldown();
  }

  @override
  void dispose() {
    _cooldownTimer?.cancel();
    super.dispose();
  }

  void _startCooldown() {
    _cooldownTimer?.cancel();
    setState(() => _secondsRemaining = _resendCooldownSeconds);
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (Timer timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_secondsRemaining <= 1) {
        timer.cancel();
        setState(() => _secondsRemaining = 0);
      } else {
        setState(() => _secondsRemaining -= 1);
      }
    });
  }

  static String? _pendingPhone(LoginState state) {
    return switch (state) {
      LoginOtpSent(:final phone) => phone,
      LoginVerifying(:final phone) => phone,
      LoginFailed(retryState: LoginOtpSent(:final phone)) => phone,
      _ => null,
    };
  }

  void _verify() {
    if (_otp.length != AppConstants.otpLength) return;
    ref.read(loginProvider.notifier).verifyOtp(_otp);
  }

  void _resend() {
    ref.read(loginProvider.notifier).resendOtp();
    _startCooldown();
  }

  @override
  Widget build(BuildContext context) {
    final LoginState state = ref.watch(loginProvider);
    final String? phone = _pendingPhone(state);

    if (phone == null) {
      // Reached without a pending phone number (deep link, page reload on
      // web, or the flow was reset) — nothing to verify against.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.go(RouteNames.login);
      });
      return const ResponsiveScaffold(body: LoadingIndicator());
    }

    final bool isVerifying = state is LoginVerifying;
    final String? errorMessage = state is LoginFailed ? state.message : null;
    final bool canResend = _secondsRemaining == 0;
    final TextTheme textTheme = context.textTheme;

    return ResponsiveScaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
          onPressed: () {
            ref.read(loginProvider.notifier).reset();
            context.go(RouteNames.login);
          },
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text('Enter verification code', style: textTheme.headlineSmall),
          const SizedBox(height: Spacing.sm),
          Text(
            'We sent a ${AppConstants.otpLength}-digit code to ${formatPhoneForDisplay(phone)}.',
            style: textTheme.bodyMedium,
          ),
          const SizedBox(height: Spacing.lg),
          if (errorMessage != null) ...<Widget>[
            InlineErrorBanner(message: errorMessage),
            const SizedBox(height: Spacing.md),
          ],
          OtpInputField(
            length: AppConstants.otpLength,
            enabled: !isVerifying,
            hasError: errorMessage != null,
            onChanged: (String value) => setState(() => _otp = value),
            onCompleted: (String value) {
              setState(() => _otp = value);
              _verify();
            },
          ),
          const SizedBox(height: Spacing.lg),
          AccessibleButton(
            label: 'Verify',
            isLoading: isVerifying,
            onPressed: (!isVerifying && _otp.length == AppConstants.otpLength)
                ? _verify
                : null,
          ),
          const SizedBox(height: Spacing.lg),
          Center(
            child: canResend
                ? AccessibleButton(
                    label: 'Resend code',
                    variant: AccessibleButtonVariant.text,
                    expand: false,
                    onPressed: isVerifying ? null : _resend,
                  )
                : Text(
                    'Resend code in ${_secondsRemaining}s',
                    style: textTheme.bodyMedium,
                  ),
          ),
        ],
      ),
    );
  }
}
