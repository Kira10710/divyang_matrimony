import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../../core/utils/validators.dart';
import '../../../../../models/enums/profile_managed_by.dart';
import '../../../../../routing/route_names.dart';
import '../../../../../shared/widgets/accessible_button.dart';
import '../../../../../shared/widgets/accessible_text_field.dart';
import '../../../../../shared/widgets/app_dropdown.dart';
import '../../../../../shared/widgets/error_view.dart';
import '../../../../../theme/app_colors.dart';
import '../../../../../theme/design_tokens.dart';
import '../../../../profile/presentation/providers/registration_draft_provider.dart';
import '../../providers/login_provider.dart';

/// Low-friction sign-up card: who the profile is for, a name and a mobile
/// number — everything else is asked after OTP, in the profile wizard.
class RegistrationCard extends ConsumerStatefulWidget {
  const RegistrationCard({super.key, this.nameFocusNode});

  /// Lets the landing page's "Let's begin" button move focus here.
  final FocusNode? nameFocusNode;

  @override
  ConsumerState<RegistrationCard> createState() => _RegistrationCardState();
}

class _RegistrationCardState extends ConsumerState<RegistrationCard> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    ref
        .read(registrationDraftProvider.notifier)
        .update(
          (RegistrationDraft d) =>
              d.copyWith(fullName: _nameController.text.trim()),
        );
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
      if (next is LoginOtpSent && previous is LoginSendingOtp)
        context.go(RouteNames.otp);
    });

    final LoginState loginState = ref.watch(loginProvider);
    final ProfileManagedBy managedBy = ref.watch(
      registrationDraftProvider.select((RegistrationDraft d) => d.managedBy),
    );
    final bool isSubmitting = loginState is LoginSendingOtp;
    final String? error = loginState is LoginFailed ? loginState.message : null;
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    return Card(
      elevation: 12,
      shadowColor: Colors.black.withValues(alpha: 0.35),
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.xl + 4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: Spacing.lg,
              vertical: Spacing.md + 2,
            ),
            color: colors.primary,
            child: Semantics(
              header: true,
              child: Text(
                'Create your profile — free',
                textAlign: TextAlign.center,
                style: text.titleLarge?.copyWith(
                  color: colors.onPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              Spacing.lg,
              Spacing.lg,
              Spacing.lg,
              Spacing.md,
            ),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  AppDropdown<ProfileManagedBy>(
                    label: 'Creating this profile for',
                    value: managedBy,
                    items: ProfileManagedBy.values,
                    itemLabel: (ProfileManagedBy m) => m.displayName,
                    enabled: !isSubmitting,
                    onChanged: (ProfileManagedBy? m) {
                      if (m == null) return;
                      ref
                          .read(registrationDraftProvider.notifier)
                          .update(
                            (RegistrationDraft d) => d.copyWith(managedBy: m),
                          );
                    },
                  ),
                  const SizedBox(height: Spacing.md),
                  AccessibleTextField(
                    label: managedBy.isSelf
                        ? 'Your full name'
                        : 'Their full name',
                    controller: _nameController,
                    focusNode: widget.nameFocusNode,
                    textInputAction: TextInputAction.next,
                    textCapitalization: TextCapitalization.words,
                    autofillHints: managedBy.isSelf
                        ? const <String>[AutofillHints.name]
                        : null,
                    enabled: !isSubmitting,
                    validator: (String? v) {
                      final String name = (v ?? '').trim();
                      if (name.isEmpty) return 'Enter a name';
                      if (name.length < 2) return 'Name is too short';
                      return null;
                    },
                  ),
                  const SizedBox(height: Spacing.md),
                  AccessibleTextField(
                    label: managedBy.isSelf
                        ? 'Mobile number'
                        : 'Your mobile number',
                    helperText: 'We’ll send a one-time code to verify it',
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    textInputAction: TextInputAction.done,
                    prefixText: '+91 ',
                    autofillHints: const <String>[
                      AutofillHints.telephoneNumber,
                    ],
                    inputFormatters: <TextInputFormatter>[
                      FilteringTextInputFormatter.digitsOnly,
                      LengthLimitingTextInputFormatter(10),
                    ],
                    validator: Validators.phone,
                    enabled: !isSubmitting,
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  if (error != null) ...<Widget>[
                    const SizedBox(height: Spacing.md),
                    InlineErrorBanner(message: error),
                  ],
                  const SizedBox(height: Spacing.lg),
                  FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.secondary,
                      foregroundColor: AppColors.onSecondary,
                      textStyle: text.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.6,
                      ),
                    ),
                    onPressed: isSubmitting ? null : _submit,
                    child: isSubmitting
                        ? const SizedBox.square(
                            dimension: 22,
                            child: CircularProgressIndicator(strokeWidth: 2.5),
                          )
                        : const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Text('REGISTER FREE'),
                              SizedBox(width: Spacing.sm),
                              Icon(Icons.arrow_forward_rounded),
                            ],
                          ),
                  ),
                  const SizedBox(height: Spacing.sm),
                  Text(
                    'By registering, you agree to our Terms of Use and Privacy Policy.',
                    textAlign: TextAlign.center,
                    style: text.bodySmall?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                  const Divider(height: Spacing.lg),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      Text('Already a member?', style: text.bodyMedium),
                      AccessibleButton(
                        label: 'Log in',
                        variant: AccessibleButtonVariant.text,
                        expand: false,
                        onPressed: () => context.go(RouteNames.login),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
