import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Thin, feature-agnostic wrapper around [FlutterSecureStorage].
///
/// Pure key/value CRUD — no knowledge of auth, tokens, or JSON shapes.
/// [SessionManager] (services/session/session_manager.dart) builds the
/// auth-specific semantics on top of this. Keeping this layer dumb means
/// it can be reused for any other secret that needs OS-keychain-backed
/// storage (e.g. a cached payment token) without touching auth code.
class SecureStorageService {
  const SecureStorageService([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            aOptions: AndroidOptions(encryptedSharedPreferences: true),
          );

  final FlutterSecureStorage _storage;

  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  Future<String?> read(String key) => _storage.read(key: key);

  Future<void> delete(String key) => _storage.delete(key: key);

  Future<void> deleteAll() => _storage.deleteAll();

  Future<bool> containsKey(String key) => _storage.containsKey(key: key);
}
