import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../../../../models/photo_model.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/photo_providers.dart';
import '../providers/my_profile_provider.dart';

class ManagePhotosScreen extends ConsumerStatefulWidget {
  const ManagePhotosScreen({super.key});

  @override
  ConsumerState<ManagePhotosScreen> createState() => _ManagePhotosScreenState();
}

class _ManagePhotosScreenState extends ConsumerState<ManagePhotosScreen> {
  final ImagePicker _picker = ImagePicker();

  Future<void> _pickAndUploadPhoto(String profileId, int displayOrder) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final XFile? xFile = await _picker.pickImage(source: ImageSource.gallery);
      if (xFile == null) return;

      final File file = File(xFile.path);

      await ref
          .read(myPhotosProvider.notifier)
          .uploadPhoto(file, profileId: profileId, displayOrder: displayOrder);

      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text('Photo uploaded and pending moderation.'),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(content: Text('Failed to upload photo: $e')),
        );
      }
    }
  }

  void _deletePhoto(String photoId) {
    final messenger = ScaffoldMessenger.of(context);
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete Photo?'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              ref
                  .read(myPhotosProvider.notifier)
                  .deletePhoto(photoId)
                  .catchError((Object e) {
                    if (mounted) {
                      messenger.showSnackBar(
                        SnackBar(content: Text('Could not delete photo: $e')),
                      );
                    }
                  });
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<PhotoModel>> photosState = ref.watch(
      myPhotosProvider,
    );
    final profileId = ref.watch(myProfileProvider.select((p) => p.value?.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Manage Photos')),
      body: profileId == null
          ? const Center(child: Text('Profile not found'))
          : photosState.when(
              loading: () => const LoadingIndicator(),
              error: (Object e, _) => Center(
                child: ErrorView(
                  message: 'Could not load photos.',
                  onRetry: () => ref.invalidate(myPhotosProvider),
                ),
              ),
              data: (List<PhotoModel> photos) {
                final List<PhotoModel> sortedPhotos = List.of(photos)
                  ..sort((a, b) => a.displayOrder.compareTo(b.displayOrder));

                return CustomScrollView(
                  slivers: [
                    SliverPadding(
                      padding: const EdgeInsets.all(Spacing.lg),
                      sliver: SliverToBoxAdapter(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              'Add up to 6 photos. First photo acts as your primary display picture.',
                              style: Theme.of(context).textTheme.bodyLarge
                                  ?.copyWith(
                                    color: Theme.of(
                                      context,
                                    ).colorScheme.onSurfaceVariant,
                                  ),
                            ),
                            const SizedBox(height: Spacing.md),
                            if (photosState.isLoading)
                              const Center(child: LinearProgressIndicator()),
                          ],
                        ),
                      ),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: Spacing.lg,
                      ),
                      sliver: SliverGrid(
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              mainAxisSpacing: Spacing.md,
                              crossAxisSpacing: Spacing.md,
                              childAspectRatio: 0.8,
                            ),
                        delegate: SliverChildBuilderDelegate((context, index) {
                          if (index < sortedPhotos.length) {
                            return _PhotoCard(
                              photo: sortedPhotos[index],
                              onDelete: () =>
                                  _deletePhoto(sortedPhotos[index].id),
                              onSetPrimary:
                                  sortedPhotos[index].moderationStatus ==
                                          'APPROVED' &&
                                      !sortedPhotos[index].isPrimary
                                  ? () => ref
                                        .read(myPhotosProvider.notifier)
                                        .setPrimaryPhoto(sortedPhotos[index].id)
                                  : null,
                            );
                          } else {
                            return _EmptyPhotoSlot(
                              onTap: photosState.isLoading
                                  ? null
                                  : () => _pickAndUploadPhoto(profileId, index),
                            );
                          }
                        }, childCount: 6),
                      ),
                    ),
                    const SliverPadding(
                      padding: EdgeInsets.only(bottom: Spacing.xxl),
                    ),
                  ],
                );
              },
            ),
    );
  }
}

class _PhotoCard extends StatelessWidget {
  const _PhotoCard({
    required this.photo,
    required this.onDelete,
    this.onSetPrimary,
  });

  final PhotoModel photo;
  final VoidCallback onDelete;
  final VoidCallback? onSetPrimary;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isApproved = photo.moderationStatus == 'APPROVED';
    final isRejected = photo.moderationStatus == 'REJECTED';

    return Stack(
      fit: StackFit.expand,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: photo.mediumUrl != null
              ? CachedNetworkImage(
                  imageUrl: photo.mediumUrl!,
                  fit: BoxFit.cover,
                  placeholder: (context, url) =>
                      const ColoredBox(color: Colors.black12),
                  errorWidget: (context, url, error) => const ColoredBox(
                    color: Colors.black12,
                    child: Icon(Icons.broken_image),
                  ),
                )
              : const ColoredBox(
                  color: Colors.black12,
                  child: Icon(Icons.image),
                ),
        ),

        // Dark overlay if rejected
        if (isRejected)
          Container(
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.6),
              borderRadius: BorderRadius.circular(12),
            ),
          ),

        // Status Badge
        Positioned(
          top: 8,
          left: 8,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: isApproved
                  ? theme.colorScheme.primaryContainer
                  : (isRejected
                        ? theme.colorScheme.errorContainer
                        : theme.colorScheme.surfaceContainerHighest),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(
              photo.moderationStatus,
              style: theme.textTheme.labelSmall?.copyWith(
                color: isApproved
                    ? theme.colorScheme.onPrimaryContainer
                    : (isRejected
                          ? theme.colorScheme.onErrorContainer
                          : theme.colorScheme.onSurfaceVariant),
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),

        // Primary Badge
        if (photo.isPrimary)
          Positioned(
            top: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: theme.colorScheme.primary,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.star_rounded,
                size: 16,
                color: theme.colorScheme.onPrimary,
              ),
            ),
          ),

        // Action Menu
        Positioned(
          bottom: 4,
          right: 4,
          child: PopupMenuButton<String>(
            icon: CircleAvatar(
              backgroundColor: theme.colorScheme.surface.withValues(alpha: 0.8),
              radius: 14,
              child: Icon(
                Icons.more_horiz,
                size: 16,
                color: theme.colorScheme.onSurface,
              ),
            ),
            onSelected: (value) {
              if (value == 'delete') onDelete();
              if (value == 'primary' && onSetPrimary != null) onSetPrimary!();
            },
            itemBuilder: (context) => [
              if (onSetPrimary != null)
                const PopupMenuItem(
                  value: 'primary',
                  child: Text('Set as primary'),
                ),
              const PopupMenuItem(
                value: 'delete',
                child: Text(
                  'Delete photo',
                  style: TextStyle(color: Colors.red),
                ),
              ),
            ],
          ),
        ),

        // Rejection reason
        if (isRejected && photo.rejectionReason != null)
          Positioned(
            bottom: 36,
            left: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer.withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                photo.rejectionReason!,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onErrorContainer,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
      ],
    );
  }
}

class _EmptyPhotoSlot extends StatelessWidget {
  const _EmptyPhotoSlot({required this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
            width: 2,
            style: BorderStyle.solid,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Center(
          child: Icon(
            Icons.add_photo_alternate_rounded,
            size: 32,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}
