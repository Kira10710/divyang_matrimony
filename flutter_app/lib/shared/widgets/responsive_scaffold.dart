import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Standard scaffold for every auth screen: keeps content readable and
/// centered on tablet/web widths (Architecture §1.2 targets Flutter Web,
/// not just phones) while staying keyboard-safe on small screens via a
/// scroll view that still fills the viewport height when content is short.
class ResponsiveScaffold extends StatelessWidget {
  const ResponsiveScaffold({
    required this.body,
    super.key,
    this.appBar,
    this.maxContentWidth = 480,
    this.padding = const EdgeInsets.all(Spacing.lg),
  });

  final Widget body;
  final PreferredSizeWidget? appBar;
  final double maxContentWidth;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: appBar,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (BuildContext context, BoxConstraints constraints) {
            return SingleChildScrollView(
              padding: padding,
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - padding.vertical,
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(maxWidth: maxContentWidth),
                    child: body,
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
