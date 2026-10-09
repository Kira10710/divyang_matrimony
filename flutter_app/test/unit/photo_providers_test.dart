import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'dart:typed_data';

import 'package:divyang_matrimony/models/photo_model.dart';
import 'package:divyang_matrimony/core/errors/exceptions.dart';
import 'package:divyang_matrimony/repositories/photo_repository.dart';
import 'package:divyang_matrimony/repositories/providers/repository_providers.dart';
import 'package:divyang_matrimony/services/image_processing_service.dart';
import 'package:divyang_matrimony/services/firebase/storage_service.dart';
import 'package:divyang_matrimony/features/profile/presentation/providers/photo_providers.dart';

class MockPhotoRepository extends Mock implements PhotoRepository {}

class MockImageProcessingService extends Mock
    implements ImageProcessingService {}

class MockDio extends Mock implements Dio {}

class MockFile extends Mock implements File {}

class FakeFile extends Fake implements File {}

void main() {
  late MockPhotoRepository mockPhotoRepo;
  late MockImageProcessingService mockImageProcessor;
  late MockDio mockDio;
  late ProviderContainer container;
  late MockFile dummyFile;

  setUpAll(() {
    registerFallbackValue(Uri.parse('http://fallback'));
    registerFallbackValue(FakeFile());
  });

  setUp(() {
    mockPhotoRepo = MockPhotoRepository();
    mockImageProcessor = MockImageProcessingService();
    mockDio = MockDio();
    dummyFile = MockFile();

    when(() => mockPhotoRepo.getMyPhotos()).thenAnswer((_) async => []);

    container = ProviderContainer(
      overrides: [
        photoRepositoryProvider.overrideWithValue(mockPhotoRepo),
        imageProcessingServiceProvider.overrideWithValue(mockImageProcessor),
        storageServiceProvider.overrideWithValue(StorageService(mockDio)),
      ],
    );
  });

  tearDown(() {
    container.dispose();
  });

  group('MyPhotosNotifier upload', () {
    final uploadSessionResponse = {
      'urls': {
        'original_url': 'https://upload.original',
        'medium_url': 'https://upload.medium',
        'thumbnail_url': 'https://upload.thumbnail',
      },
      'paths': {
        'storage_path': 'profiles/123/original.jpg',
        'medium_path': 'profiles/123/medium.jpg',
        'thumbnail_path': 'profiles/123/thumbnail.jpg',
      },
    };

    final mockPhoto = PhotoModel(
      id: 'photo-1',
      profileId: '123',
      displayOrder: 0,
      isPrimary: false,
      moderationStatus: 'PENDING',
      createdAt: DateTime.now(),
    );

    setUp(() {
      when(() => mockImageProcessor.processImage(any())).thenAnswer(
        (_) async => ImageVariants(
          originalBytes: Uint8List.fromList([1]),
          mediumBytes: Uint8List.fromList([2]),
          thumbnailBytes: Uint8List.fromList([3]),
        ),
      );
    });

    test('successful upload', () async {
      when(
        () => mockPhotoRepo.createUploadSession(),
      ).thenAnswer((_) async => uploadSessionResponse);

      when(
        () => mockDio.put<dynamic>(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenAnswer(
        (_) async => Response(requestOptions: RequestOptions(path: '')),
      );

      when(
        () => mockPhotoRepo.registerPhoto(any()),
      ).thenAnswer((_) async => mockPhoto);

      final notifier = container.read(myPhotosProvider.notifier);
      await notifier.uploadPhoto(dummyFile, profileId: '123', displayOrder: 0);

      verify(() => mockPhotoRepo.createUploadSession()).called(1);
      verify(
        () => mockDio.put<dynamic>(
          'https://upload.original',
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).called(1);
      verify(
        () => mockDio.put<dynamic>(
          'https://upload.medium',
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).called(1);
      verify(
        () => mockDio.put<dynamic>(
          'https://upload.thumbnail',
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).called(1);

      final captured = verify(
        () => mockPhotoRepo.registerPhoto(captureAny()),
      ).captured;
      final capturedMap = captured.first as Map<String, dynamic>;
      expect(capturedMap['storage_path'], 'profiles/123/original.jpg');

      final state = container.read(myPhotosProvider);
      expect(state.value, contains(mockPhoto));
    });

    test('failed HTTP PUT request throws and does not register', () async {
      when(
        () => mockPhotoRepo.createUploadSession(),
      ).thenAnswer((_) async => uploadSessionResponse);

      when(
        () => mockDio.put<dynamic>(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenThrow(DioException(requestOptions: RequestOptions(path: '')));

      final notifier = container.read(myPhotosProvider.notifier);

      await expectLater(
        notifier.uploadPhoto(dummyFile, profileId: '123', displayOrder: 0),
        throwsA(isA<ServerException>()),
      );

      verify(() => mockPhotoRepo.createUploadSession()).called(1);
      verifyNever(() => mockPhotoRepo.registerPhoto(any()));
    });

    test('registration failure throws', () async {
      when(
        () => mockPhotoRepo.createUploadSession(),
      ).thenAnswer((_) async => uploadSessionResponse);

      when(
        () => mockDio.put<dynamic>(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenAnswer(
        (_) async => Response(requestOptions: RequestOptions(path: '')),
      );

      when(
        () => mockPhotoRepo.registerPhoto(any()),
      ).thenThrow(Exception('Registration failed'));

      final notifier = container.read(myPhotosProvider.notifier);

      await expectLater(
        notifier.uploadPhoto(dummyFile, profileId: '123', displayOrder: 0),
        throwsA(isA<Exception>()),
      );

      verify(() => mockPhotoRepo.registerPhoto(any())).called(1);

      final state = container.read(myPhotosProvider);
      expect(state.value, isEmpty);
    });
  });
}
