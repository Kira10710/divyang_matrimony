import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../theme/design_tokens.dart';

/// A boxed one-time-password input: [length] visual digit boxes backed by a
/// single, real (but visually hidden) [TextField] — the standard approach
/// for a custom OTP widget that still gets real text-input behavior for
/// free: platform SMS autofill, paste, IME, and screen-reader focus/typing,
/// none of which a hand-rolled per-box `FocusNode` chain reliably gets.
class OtpInputField extends StatefulWidget {
  const OtpInputField({
    required this.length,
    required this.onChanged,
    super.key,
    this.onCompleted,
    this.hasError = false,
    this.enabled = true,
    this.autofocus = true,
  });

  final int length;
  final ValueChanged<String> onChanged;
  final ValueChanged<String>? onCompleted;
  final bool hasError;
  final bool enabled;
  final bool autofocus;

  @override
  State<OtpInputField> createState() => _OtpInputFieldState();
}

class _OtpInputFieldState extends State<OtpInputField> {
  late final TextEditingController _controller = TextEditingController();
  late final FocusNode _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleChanged(String value) {
    widget.onChanged(value);
    if (value.length == widget.length) {
      widget.onCompleted?.call(value);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;

    return Semantics(
      textField: true,
      label: 'One-time password, ${widget.length} digits',
      child: GestureDetector(
        onTap: () => _focusNode.requestFocus(),
        child: Stack(
          alignment: Alignment.center,
          children: <Widget>[
            AnimatedBuilder(
              animation: Listenable.merge(<Listenable>[
                _controller,
                _focusNode,
              ]),
              builder: (BuildContext context, Widget? _) {
                final String value = _controller.text;
                return Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: List<Widget>.generate(widget.length, (int index) {
                    final bool filled = index < value.length;
                    final bool isCursor =
                        index == value.length &&
                        _focusNode.hasFocus &&
                        widget.enabled;
                    final Color borderColor = widget.hasError
                        ? colors.error
                        : isCursor
                        ? colors.primary
                        : colors.outline;
                    return Container(
                      width: 44,
                      height: 56,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(AppRadius.md),
                        border: Border.all(
                          color: borderColor,
                          width: isCursor || widget.hasError ? 2 : 1,
                        ),
                      ),
                      child: Text(
                        filled ? value[index] : '',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                    );
                  }),
                );
              },
            ),
            // The real input — fully functional, just invisible; screen
            // readers and platform autofill interact with this, not the
            // decorative boxes above.
            Opacity(
              opacity: 0,
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                enabled: widget.enabled,
                autofocus: widget.autofocus,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                autofillHints: const <String>[AutofillHints.oneTimeCode],
                inputFormatters: <TextInputFormatter>[
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(widget.length),
                ],
                onChanged: _handleChanged,
                decoration: const InputDecoration(
                  counterText: '',
                  border: InputBorder.none,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
