import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

class ProfileRepository {
  ProfileRepository(this._dio);

  final Dio _dio;

  String get _baseUrl => _dio.options.baseUrl.replaceFirst('/api/v1', '');

  String absoluteMediaUrl(String relativeOrAbsolutePath) {
    if (relativeOrAbsolutePath.startsWith('http://') ||
        relativeOrAbsolutePath.startsWith('https://')) {
      return relativeOrAbsolutePath;
    }
    if (relativeOrAbsolutePath.startsWith('/')) {
      return '$_baseUrl$relativeOrAbsolutePath';
    }
    return '$_baseUrl/$relativeOrAbsolutePath';
  }

  Future<Map<String, dynamic>> getMyProfile() async {
    final response = await _dio.get('/profile');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateProfile(
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.patch('/profile', data: payload);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> uploadAvatar(String filePath) async {
    final fileName = filePath.split(RegExp(r'[\\/]+')).last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath, filename: fileName),
    });

    final response = await _dio.post(
      '/profile/avatar',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return response.data as Map<String, dynamic>;
  }
}

final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  return ProfileRepository(ref.read(dioProvider));
});
