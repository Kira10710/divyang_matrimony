import '../../core/constants/api_endpoints.dart';
import '../../core/errors/exception_mapper.dart';
import '../../core/network/api_client.dart';
import '../../models/photo_model.dart';
import '../photo_repository.dart';

class PhotoRepositoryImpl implements PhotoRepository {
  const PhotoRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<List<PhotoModel>> getMyPhotos() async {
    try {
      final Object? data = await _api.get(ApiEndpoints.myPhotos);
      if (data is! Map<String, dynamic> || !data.containsKey('photos')) {
        return <PhotoModel>[];
      }
      final List<dynamic> photosList = data['photos'] as List<dynamic>;
      return photosList
          .whereType<Map<String, dynamic>>()
          .map(PhotoModel.fromJson)
          .toList();
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<Map<String, dynamic>> createUploadSession() async {
    try {
      final Object? data = await _api.post(
        '${ApiEndpoints.myPhotos}/upload-sessions',
      );
      if (data is! Map<String, dynamic>) {
        throw const FormatException(
          'Expected a JSON object from createUploadSession',
        );
      }
      return data;
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<PhotoModel> registerPhoto(Map<String, dynamic> body) async {
    try {
      final Object? data = await _api.post(ApiEndpoints.myPhotos, data: body);
      if (data is! Map<String, dynamic>) {
        throw const FormatException(
          'Expected a JSON object from registerPhoto',
        );
      }
      return PhotoModel.fromJson(data);
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<void> deletePhoto(String photoId) async {
    try {
      await _api.delete('${ApiEndpoints.myPhotos}/$photoId');
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<void> setPrimaryPhoto(String photoId) async {
    try {
      await _api.patch('${ApiEndpoints.myPhotos}/$photoId/primary');
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }
}
