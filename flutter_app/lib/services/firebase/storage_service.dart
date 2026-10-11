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
    required int maxBytes,
  }) async {
    await Future.wait(<Future<void>>[
      _uploadBytes(originalUrl, originalBytes, maxBytes),
      _uploadBytes(mediumUrl, mediumBytes, maxBytes),
      _uploadBytes(thumbnailUrl, thumbnailBytes, maxBytes),
    ]);
  }

  Future<void> _uploadBytes(String url, List<int> bytes, int maxBytes) async {
    try {
      await _dio.put<dynamic>(
        url,
        data: Uint8List.fromList(bytes),
        options: Options(
          headers: <String, String>{
            'Content-Type': 'image/jpeg',
            'x-goog-content-length-range': '0,$maxBytes',
          },
        ),
      );
    } on DioException {
      throw const ServerException('Failed to upload image. Please try again.');
    }
  }
}
