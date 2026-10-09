/// Profile/document verification status.
///
/// See Architecture Section 4.11 for the workflow:
/// User uploads -> PENDING -> Admin reviews -> APPROVED | REJECTED
enum VerificationStatus {
  none('Not Submitted'),
  pending('Pending Review'),
  approved('Verified'),
  rejected('Rejected');

  final String displayName;
  const VerificationStatus(this.displayName);
}
