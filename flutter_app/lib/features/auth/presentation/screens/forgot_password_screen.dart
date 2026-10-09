import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/utils/validators.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/extensions/context_extensions.dart';
import '../../../../shared/widgets/accessible_button.dart';
import '../../../../shared/widgets/accessible_text_field.dart';
import '../../../../shared/widgets/responsive_scaffold.dart';
import '../../../../theme/design_tokens.dart';

/// Admin password recovery.
///
/// There is deliberately no `POST /auth/forgot-password` call here: the
/// backend has no such endpoint (`backend/app/api/v1/auth.py` only exposes
/// send-otp/verify-otp/login-admin/refresh/logout/sessions/me) — admin
/// accounts are provisioned directly via `scripts/create_admin.py`, per
/// Architecture §7.8 ("issued credentials, not self-registering"). End
/// users have no password at all to forget (OTP is their only credential).
///
/// Rather than fabricate a fake "reset link sent" success state against a
/// non-existent endpoint, this screen does the honest, still-useful thing:
/// open a pre-filled email to a real support address so a human can verify
/// the requester's identity and reset the password out of band.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key, this.prefilledEmail});

  /// Email typed on [AdminLoginScreen] before navigating here, if any.
  final String? prefilledEmail;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  late final TextEditingController _emailController = TextEditingController(
    text: widget.prefilledEmail,
  );
  bool _isLaunching = false;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  static String _encodeQueryParameters(Map<String, String> params) {
    return params.entries
        .map(
          (MapEntry<String, String> e) =>
              '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value)}',
        )
        .join('&');
  }

  Future<void> _emailSupport() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();

    final String email = _emailController.text.trim();
    final Uri uri = Uri(
      scheme: 'mailto',
      path: AppConstants.supportEmail,
      query: _encodeQueryParameters(<String, String>{
        'subject': 'Admin password reset request',
        'body':
            'Admin account email: $email\n\nPlease verify my identity and reset my password.',
      }),
    );

    setState(() => _isLaunching = true);
    bool launched = false;
    try {
      launched = await launchUrl(uri);
    } finally {
      if (mounted) setState(() => _isLaunching = false);
    }

    if (!launched && mounted) {
      context.showSnackBar(
        'Could not open a mail app. Please email ${AppConstants.supportEmail} directly.',
        isError: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = context.textTheme;

    return ResponsiveScaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
          onPressed: () => context.canPop()
              ? context.pop()
              : context.go(RouteNames.adminLogin),
        ),
      ),
      body: Form(
        key: _formKey,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.lock_reset_rounded,
              size: 48,
              color: context.colors.primary,
            ),
            const SizedBox(height: Spacing.md),
            Text(
              'Forgot your password?',
              style: textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: Spacing.sm),
            Text(
              'Admin accounts are issued and managed directly — there is no self-service password '
              "reset. Confirm your account email below and we'll open a message to our support team "
              'to verify your identity and reset it for you.',
              style: textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: Spacing.lg),
            AccessibleTextField(
              label: 'Admin email address',
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.done,
              validator: Validators.email,
              enabled: !_isLaunching,
              onFieldSubmitted: (_) => _emailSupport(),
            ),
            const SizedBox(height: Spacing.lg),
            AccessibleButton(
              label: 'Email support',
              icon: Icons.mail_outline,
              isLoading: _isLaunching,
              onPressed: _isLaunching ? null : _emailSupport,
            ),
            const SizedBox(height: Spacing.md),
            Text(
              'Or reach us directly at ${AppConstants.supportEmail}',
              style: textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
