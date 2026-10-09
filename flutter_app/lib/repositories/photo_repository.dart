import '../models/photo_model.dart';

abstract class PhotoRepository {
  /// GET /profiles/me/photos
  Future<List<PhotoModel>> getMyPhotos();

  /// POST /profiles/me/photos/upload-sessions
  Future<Map<String, dynamic>> createUploadSession();

  /// POST /profiles/me/photos
  Future<PhotoModel> registerPhoto(Map<String, dynamic> body);

  /// DELETE /profiles/me/photos/{photoId}
  Future<void> deletePhoto(String photoId);

  /// PATCH /profiles/me/photos/{photoId}/primary
  Future<void> setPrimaryPhoto(String photoId);
}
