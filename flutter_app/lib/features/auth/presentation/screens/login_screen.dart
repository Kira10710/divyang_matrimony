import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/utils/validators.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/extensions/context_extensions.dart';
import '../../../../shared/widgets/accessible_button.dart';
import '../../../../shared/widgets/accessible_text_field.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/responsive_scaffold.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/login_provider.dart';

/// Phone entry — step 1 of the unified login/registration flow
/// (`POST /auth/send-otp`). Serves both new and returning end users; the
/// backend doesn't distinguish them until OTP verification decides whether
/// to create a new `users` row.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _phoneController = TextEditingController();

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    ref
        .read(loginProvider.notifier)
        .sendOtp(Validators.phoneToE164(_phoneController.text));
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<LoginState>(loginProvider, (
      LoginState? previous,
      LoginState next,
    ) {
      if (next is LoginOtpSent) {
        context.go(RouteNames.otp);
      }
    });

    final LoginState state = ref.watch(loginProvider);
    final bool isSubmitting = state is LoginSendingOtp;
    final String? errorMessage = state is LoginFailed ? state.message : null;
    final TextTheme textTheme = context.textTheme;

    return ResponsiveScaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
          onPressed: () => context.go(RouteNames.welcome),
        ),
      ),
      body: Form(
        key: _formKey,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text('Login or sign up', style: textTheme.headlineSmall),
            const SizedBox(height: Spacing.sm),
            Text(
              "We'll text you a one-time code to verify your number — no password needed.",
              style: textTheme.bodyMedium,
            ),
            const SizedBox(height: Spacing.lg),
            if (errorMessage != null) ...<Widget>[
              InlineErrorBanner(message: errorMessage),
              const SizedBox(height: Spacing.md),
            ],
            AccessibleTextField(
              label: 'Mobile number',
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              textInputAction: TextInputAction.done,
              prefixText: '+91 ',
              autofillHints: const <String>[AutofillHints.telephoneNumber],
              inputFormatters: <TextInputFormatter>[
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(10),
              ],
              validator: Validators.phone,
              enabled: !isSubmitting,
              autofocus: true,
              onFieldSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: Spacing.lg),
            AccessibleButton(
              label: 'Send OTP',
              isLoading: isSubmitting,
              onPressed: isSubmitting ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}
