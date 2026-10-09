import 'package:flutter/material.dart';
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
import '../providers/admin_login_provider.dart';

/// Admin email+password sign-in (`POST /auth/login-admin`, Architecture §6).
/// Not the primary flow for this app — reached only via the low-emphasis
/// "Admin sign in" link on [WelcomeScreen] — admin accounts are issued to
/// internal staff, not self-registered (Architecture §7.8).
class AdminLoginScreen extends ConsumerStatefulWidget {
  const AdminLoginScreen({super.key});

  @override
  ConsumerState<AdminLoginScreen> createState() => _AdminLoginScreenState();
}

class _AdminLoginScreenState extends ConsumerState<AdminLoginScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    ref
        .read(adminLoginProvider.notifier)
        .submit(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
  }

  @override
  Widget build(BuildContext context) {
    final AdminLoginState state = ref.watch(adminLoginProvider);
    final bool isSubmitting = state is AdminLoginSubmitting;
    final String? errorMessage = state is AdminLoginFailed
        ? state.message
        : null;
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
            Text('Admin sign in', style: textTheme.headlineSmall),
            const SizedBox(height: Spacing.sm),
            Text(
              'For platform staff only. End users sign in with their phone number.',
              style: textTheme.bodyMedium,
            ),
            const SizedBox(height: Spacing.lg),
            if (errorMessage != null) ...<Widget>[
              InlineErrorBanner(message: errorMessage),
              const SizedBox(height: Spacing.md),
            ],
            AccessibleTextField(
              label: 'Email address',
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              autofillHints: const <String>[
                AutofillHints.username,
                AutofillHints.email,
              ],
              validator: Validators.email,
              enabled: !isSubmitting,
              autofocus: true,
            ),
            const SizedBox(height: Spacing.md),
            AccessibleTextField(
              label: 'Password',
              controller: _passwordController,
              obscureText: _obscurePassword,
              textInputAction: TextInputAction.done,
              autofillHints: const <String>[AutofillHints.password],
              validator: Validators.password,
              enabled: !isSubmitting,
              onFieldSubmitted: (_) => _submit(),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscurePassword
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
                tooltip: _obscurePassword ? 'Show password' : 'Hide password',
                onPressed: () =>
                    setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: AccessibleButton(
                label: 'Forgot password?',
                variant: AccessibleButtonVariant.text,
                expand: false,
                onPressed: isSubmitting
                    ? null
                    : () => context.push(
                        RouteNames.forgotPassword,
                        extra: _emailController.text.trim(),
                      ),
              ),
            ),
            const SizedBox(height: Spacing.sm),
            AccessibleButton(
              label: 'Sign in',
              isLoading: isSubmitting,
              onPressed: isSubmitting ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}
