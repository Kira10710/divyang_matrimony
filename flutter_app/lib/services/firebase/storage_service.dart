import 'dart:typed_data';
import 'package:dio/dio.dart';

import '../../core/errors/exceptions.dart';

/// Client for uploading photo variants to pre-signed URLs.
class StorageService {
  const StorageService(this._dio);

  final Dio _dio;

  /// Uploads the 3 image variants using HTTP PUT to the provided signed URLs.
  Future<void> uploadProfilePhotoVariants({
    required String originalUrl,
    required List<int> originalBytes,
    required String mediumUrl,
    required List<int> mediumBytes,
    required String thumbnailUrl,
    required List<int> thumbnailBytes,
  }) async {
    await Future.wait(<Future<void>>[
      _uploadBytes(originalUrl, originalBytes),
      _uploadBytes(mediumUrl, mediumBytes),
      _uploadBytes(thumbnailUrl, thumbnailBytes),
    ]);
  }

  Future<void> _uploadBytes(String url, List<int> bytes) async {
    try {
      await _dio.put<dynamic>(
        url,
        data: Uint8List.fromList(bytes),
        options: Options(
          headers: const <String, String>{'Content-Type': 'image/jpeg'},
        ),
      );
    } on DioException {
      throw const ServerException('Failed to upload image. Please try again.');
    }
  }
}
