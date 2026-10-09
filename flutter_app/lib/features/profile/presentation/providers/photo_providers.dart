import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../models/photo_model.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../../../../services/image_processing_service.dart';
import '../../../../services/firebase/storage_service.dart';
import 'my_profile_provider.dart';

// Provides instances of the services
final imageProcessingServiceProvider = Provider(
  (ref) => const ImageProcessingService(),
);

// StorageService now requires a standard Dio client (not authenticated)
final storageServiceProvider = Provider((ref) => StorageService(Dio()));

class MyPhotosNotifier extends AsyncNotifier<List<PhotoModel>> {
  @override
  Future<List<PhotoModel>> build() async {
    return ref.read(photoRepositoryProvider).getMyPhotos();
  }

  Future<void> uploadPhoto(
    File file, {
    required String profileId,
    required int displayOrder,
    bool isPrimary = false,
  }) async {
    final previousState = state;
    state = const AsyncLoading();
    try {
      final imageProcessor = ref.read(imageProcessingServiceProvider);
      final variants = await imageProcessor.processImage(file);

      // 1. Request upload session (authenticated)
      final session = await ref
          .read(photoRepositoryProvider)
          .createUploadSession();
      final Map<String, dynamic> urls = session['urls'] as Map<String, dynamic>;
      final Map<String, dynamic> paths = session['paths'] as Map<String, dynamic>;

      // 2. Upload bytes to signed URLs (unauthenticated Dio)
      final storageService = ref.read(storageServiceProvider);
      await storageService.uploadProfilePhotoVariants(
        originalUrl: urls['original_url'] as String,
        originalBytes: variants.originalBytes,
        mediumUrl: urls['medium_url'] as String,
        mediumBytes: variants.mediumBytes,
        thumbnailUrl: urls['thumbnail_url'] as String,
        thumbnailBytes: variants.thumbnailBytes,
      );

      // 3. Register paths with the backend
      final newPhoto = await ref.read(photoRepositoryProvider).registerPhoto({
        'storage_path': paths['storage_path'],
        'medium_path': paths['medium_path'],
        'thumbnail_path': paths['thumbnail_path'],
        'display_order': displayOrder,
        'is_primary': isPrimary,
      });

      state = AsyncData([...previousState.value ?? [], newPhoto]);
      ref.invalidate(myProfileProvider);
    } catch (e) {
      state = previousState;
      rethrow;
    }
  }

  Future<void> deletePhoto(String photoId) async {
    final previousState = state;
    state = const AsyncLoading();
    try {
      await ref.read(photoRepositoryProvider).deletePhoto(photoId);
      state = AsyncData(
        (previousState.value ?? []).where((p) => p.id != photoId).toList(),
      );
      ref.invalidate(myProfileProvider);
    } catch (e) {
      state = previousState;
      rethrow;
    }
  }

  Future<void> setPrimaryPhoto(String photoId) async {
    final previousState = state;
    state = const AsyncLoading();
    try {
      await ref.read(photoRepositoryProvider).setPrimaryPhoto(photoId);
      final updatedPhotos = (previousState.value ?? []).map((p) {
        if (p.id == photoId) return p.copyWith(isPrimary: true);
        return p.copyWith(isPrimary: false);
      }).toList();
      state = AsyncData(updatedPhotos);
      ref.invalidate(myProfileProvider);
    } catch (e) {
      state = previousState;
      rethrow;
    }
  }
}

final myPhotosProvider =
    AsyncNotifierProvider<MyPhotosNotifier, List<PhotoModel>>(
      MyPhotosNotifier.new,
    );
