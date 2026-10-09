class PhotoModel {
  const PhotoModel({
    required this.id,
    required this.profileId,
    required this.displayOrder,
    required this.isPrimary,
    required this.moderationStatus,
    required this.createdAt,
    this.originalUrl,
    this.mediumUrl,
    this.thumbnailUrl,
    this.rejectionReason,
  });

  factory PhotoModel.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic>? signedUrls =
        json['signed_urls'] as Map<String, dynamic>?;

    return PhotoModel(
      id: json['id'] as String,
      profileId: json['profile_id'] as String,
      originalUrl: signedUrls?['original_url'] as String?,
      mediumUrl: signedUrls?['medium_url'] as String?,
      thumbnailUrl: signedUrls?['thumbnail_url'] as String?,
      displayOrder: json['display_order'] as int? ?? 0,
      isPrimary: json['is_primary'] as bool? ?? false,
      moderationStatus: json['moderation_status'] as String? ?? 'PENDING',
      rejectionReason: json['rejection_reason'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  final String id;
  final String profileId;
  final String? originalUrl;
  final String? mediumUrl;
  final String? thumbnailUrl;
  final int displayOrder;
  final bool isPrimary;
  final String moderationStatus;
  final String? rejectionReason;
  final DateTime createdAt;

  PhotoModel copyWith({
    bool? isPrimary,
    String? moderationStatus,
    int? displayOrder,
  }) {
    return PhotoModel(
      id: id,
      profileId: profileId,
      originalUrl: originalUrl,
      mediumUrl: mediumUrl,
      thumbnailUrl: thumbnailUrl,
      displayOrder: displayOrder ?? this.displayOrder,
      isPrimary: isPrimary ?? this.isPrimary,
      moderationStatus: moderationStatus ?? this.moderationStatus,
      rejectionReason: rejectionReason,
      createdAt: createdAt,
    );
  }
}
