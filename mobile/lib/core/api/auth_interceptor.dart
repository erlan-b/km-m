import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_storage.dart';

class AuthInterceptor extends Interceptor {
  AuthInterceptor({required this.dio, required this.ref});

  final Dio dio;
  final Ref ref;
  bool _isRefreshing = false;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final storage = ref.read(secureStorageProvider);
    final accessToken = await storage.readAccessToken();

    if (accessToken != null) {
      options.headers['Authorization'] = 'Bearer $accessToken';
    }

    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401 || _isRefreshing) {
      return handler.next(err);
    }

    _isRefreshing = true;

    try {
      final storage = ref.read(secureStorageProvider);
      final refreshToken = await storage.readRefreshToken();

      if (refreshToken == null) {
        await storage.clearAll();
        return handler.next(err);
      }

      final response = await dio.post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
        options: Options(headers: {'Authorization': ''}),
      );

      final newAccessToken = response.data['access_token'] as String;
      final newRefreshToken = response.data['refresh_token'] as String;

      await storage.writeTokens(
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
      );

      // Retry original request with new token
      final retryOptions = err.requestOptions;
      retryOptions.headers['Authorization'] = 'Bearer $newAccessToken';

      final retryResponse = await dio.fetch(retryOptions);
      return handler.resolve(retryResponse);
    } on DioException {
      final storage = ref.read(secureStorageProvider);
      await storage.clearAll();
      return handler.next(err);
    } finally {
      _isRefreshing = false;
    }
  }
}
