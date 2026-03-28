import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/storage/secure_storage.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  const AuthState({required this.status, this.userId, this.accessToken});

  final AuthStatus status;
  final int? userId;
  final String? accessToken;

  bool get isAuthenticated => status == AuthStatus.authenticated;
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._storage) : super(const AuthState(status: AuthStatus.unknown));

  final SecureStorageService _storage;

  Future<void> checkAuth() async {
    final hasTokens = await _storage.hasTokens();
    if (hasTokens) {
      state = const AuthState(status: AuthStatus.authenticated);
    } else {
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  Future<void> setAuthenticated({required String accessToken, required String refreshToken}) async {
    await _storage.writeTokens(accessToken: accessToken, refreshToken: refreshToken);
    state = AuthState(status: AuthStatus.authenticated, accessToken: accessToken);
  }

  Future<void> logout() async {
    await _storage.clearAll();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final storage = ref.read(secureStorageProvider);
  return AuthNotifier(storage);
});
