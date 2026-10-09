/// Subscription tier enum.
///
/// See Architecture Section 4.9:
/// - Free: blurred browse, 3 interests/day, no contact reveal
/// - Basic: full profiles, 10 interests/day, contact on mutual interest
/// - Premium: unlimited interests, profile boost, "who viewed me"
enum SubscriptionTier {
  free('Free'),
  basic('Basic'),
  premium('Premium');

  final String displayName;
  const SubscriptionTier(this.displayName);
}
