import 'dart:io';
import 'dart:typed_data';
import 'package:image/image.dart' as img;

/// Client-side image resizing service (Architecture Section 4.2).
/// Resizes a selected image into three variants: original (~1600px), medium (~800px),
/// and thumbnail (~200px), stripping EXIF data.
class ImageProcessingService {
  const ImageProcessingService();

  Future<ImageVariants> processImage(File sourceFile) async {
    final Uint8List bytes = await sourceFile.readAsBytes();
    // decodeImage strips EXIF by default in the image package
    final img.Image? originalImage = img.decodeImage(bytes);

    if (originalImage == null) {
      throw const FormatException('Could not decode image file.');
    }

    // Original: cap at 1600px width/height
    final img.Image original = _resizeIfLarger(originalImage, 1600);
    // Medium: cap at 800px
    final img.Image medium = _resizeIfLarger(original, 800);
    // Thumbnail: cap at 200px
    final img.Image thumbnail = _resizeIfLarger(medium, 200);

    return ImageVariants(
      originalBytes: img.encodeJpg(original, quality: 85),
      mediumBytes: img.encodeJpg(medium, quality: 85),
      thumbnailBytes: img.encodeJpg(thumbnail, quality: 85),
    );
  }

  img.Image _resizeIfLarger(img.Image image, int maxSize) {
    if (image.width <= maxSize && image.height <= maxSize) {
      return image;
    }
    if (image.width > image.height) {
      return img.copyResize(image, width: maxSize);
    } else {
      return img.copyResize(image, height: maxSize);
    }
  }
}

class ImageVariants {
  const ImageVariants({
    required this.originalBytes,
    required this.mediumBytes,
    required this.thumbnailBytes,
  });

  final Uint8List originalBytes;
  final Uint8List mediumBytes;
  final Uint8List thumbnailBytes;
}
